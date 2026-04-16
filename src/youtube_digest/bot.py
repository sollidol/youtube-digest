import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import youtube_digest.config as cfg
from . import cache
from .config import settings, MODELS, MODEL_LABELS
from .ideas import save_ideas
from .llm import LLMError, analyze
from .metadata import fetch_video_meta
from .transcript import extract_video_id, fetch_transcript

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

router = Router()

TG_LIMIT = 4096



async def _safe_send(msg, text: str, edit: bool = False, reply_markup=None):
    chunks = []
    while len(text) > TG_LIMIT:
        split_at = text.rfind("\n", 0, TG_LIMIT)
        if split_at < 100:
            split_at = TG_LIMIT
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    chunks.append(text)

    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        km = reply_markup if is_last else None
        if i == 0 and edit:
            try:
                await msg.edit_text(chunk, parse_mode="Markdown", reply_markup=km)
            except TelegramBadRequest:
                await msg.edit_text(chunk, reply_markup=km)
        else:
            try:
                await msg.answer(chunk, parse_mode="Markdown", reply_markup=km)
            except TelegramBadRequest:
                await msg.answer(chunk, reply_markup=km)


def is_owner(message: Message) -> bool:
    return message.from_user and message.from_user.id == settings.telegram_owner_id


def is_owner_cb(callback: CallbackQuery) -> bool:
    return callback.from_user and callback.from_user.id == settings.telegram_owner_id


def _current_model_alias() -> str:
    for alias, model_id in MODELS.items():
        if model_id == cfg.active_model:
            return alias
    return cfg.active_model


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_owner(message):
        return
    await message.answer(
        "Кидай ссылку на YouTube — получишь идеи.\n\n"
        f"Модель: *{_current_model_alias()}* (`{cfg.active_model}`)\n"
        "Сменить: /model",
        parse_mode="Markdown",
    )


@router.message(F.text == "/model", is_owner)
async def cmd_model(message: Message):
    buttons = []
    for alias, label in MODEL_LABELS.items():
        current = " ✓" if MODELS[alias] == cfg.active_model else ""
        buttons.append([InlineKeyboardButton(
            text=f"{label}{current}",
            callback_data=f"model:{alias}",
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери модель для анализа:", reply_markup=kb)


@router.callback_query(F.data.startswith("model:"), is_owner_cb)
async def handle_model_switch(callback: CallbackQuery):
    alias = callback.data.split(":", 1)[1]
    model_id = MODELS.get(alias)
    if not model_id:
        await callback.answer("Неизвестная модель", show_alert=True)
        return

    cfg.active_model = model_id
    await callback.answer(f"Модель: {alias}")
    await callback.message.edit_text(f"✅ Модель переключена на *{alias}*\n`{model_id}`", parse_mode="Markdown")


@router.message(F.text, is_owner)
async def handle_link(message: Message):
    video_id = extract_video_id(message.text)
    if not video_id:
        await message.answer("Не вижу YouTube-ссылку. Кинь ещё раз.")
        return

    status = await message.answer("⏳ Тяну транскрипт...")

    try:
        transcript = await asyncio.to_thread(fetch_transcript, video_id)
    except Exception as e:
        log.warning("Transcript failed for %s: %s", video_id, e)
        await status.edit_text(
            "❌ Не удалось получить субтитры. Возможно, у видео нет авто-сабов."
        )
        return

    await status.edit_text("🧠 Извлекаю идеи...")

    meta = await fetch_video_meta(video_id)

    try:
        result = await analyze(transcript, meta["title"], meta["channel"])
    except LLMError as e:
        log.warning("LLM error: %s", e)
        await status.edit_text(f"❌ {e}")
        return
    except Exception as e:
        log.error("LLM failed: %s", e)
        await status.edit_text("❌ Ошибка LLM. Попробуй ещё раз.")
        return

    ideas = result.get("ideas", [])
    url = f"https://www.youtube.com/watch?v={video_id}"

    if not ideas:
        await status.edit_text(
            f"📹 {meta['title']}\n🎙 {meta['channel']}\n\n"
            "🤷 Применимых идей не нашлось."
        )
        return

    cache.put(video_id, {
        "ideas": ideas,
        "title": meta["title"],
        "channel": meta["channel"],
        "url": url,
        "selected": set(range(len(ideas))),
    })

    try:
        await _send_ideas(status, video_id)
    except Exception as e:
        log.error("Failed to send ideas: %s", e, exc_info=True)
        await status.edit_text(f"❌ Ошибка отправки: {type(e).__name__}: {e}")


async def _send_ideas(status_msg, video_id: str):
    cached = cache.get(video_id)
    ideas = cached["ideas"]
    chat_id = status_msg.chat.id

    header = f"📹 {cached['title']}\n🎙 {cached['channel']}\n\n💡 Идеи ({len(ideas)}):"
    await status_msg.edit_text(header)

    msg_ids = []
    for i, idea in enumerate(ideas):
        tags = ", ".join(f"#{t}" for t in idea.get("tags", []))
        text = f"*{i + 1}. {idea['title']}*\n{idea['description']}\n_{tags}_"
        kb = _idea_kb(video_id, i, selected=True)
        try:
            sent = await status_msg.answer(text, parse_mode="Markdown", reply_markup=kb)
        except TelegramBadRequest:
            sent = await status_msg.answer(text, reply_markup=kb)
        msg_ids.append(sent.message_id)

    # Summary message with save/cancel
    summary = await status_msg.answer("⬆️ Отметь нужные идеи, затем сохрани", reply_markup=_summary_kb(video_id))

    cached["msg_ids"] = msg_ids
    cached["summary_msg_id"] = summary.message_id
    cached["chat_id"] = chat_id
    cache.update(video_id)


def _idea_kb(video_id: str, idx: int, selected: bool) -> InlineKeyboardMarkup:
    if selected:
        btn = InlineKeyboardButton(text="✅ Взято", callback_data=f"toggle:{video_id}:{idx}")
    else:
        btn = InlineKeyboardButton(text="❌ Не берём", callback_data=f"toggle:{video_id}:{idx}")
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])


def _summary_kb(video_id: str) -> InlineKeyboardMarkup:
    cached = cache.get(video_id)
    selected = cached["selected"]
    total = len(cached["ideas"])

    rows = []
    if selected:
        label = f"💾 Сохранить ({len(selected)}/{total})" if len(selected) < total else f"💾 Сохранить все ({total})"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"save_ideas:{video_id}")])
    rows.append([InlineKeyboardButton(text="❌ Не сохранять", callback_data="cancel_ideas")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _update_summary(bot: Bot, video_id: str):
    cached = cache.get(video_id)
    if not cached or "summary_msg_id" not in cached:
        return
    try:
        await bot.edit_message_reply_markup(
            chat_id=cached["chat_id"],
            message_id=cached["summary_msg_id"],
            reply_markup=_summary_kb(video_id),
        )
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("toggle:"), is_owner_cb)
async def handle_toggle_idea(callback: CallbackQuery):
    _, video_id, idx_str = callback.data.split(":", 2)
    idx = int(idx_str)
    cached = cache.get(video_id)
    if not cached or "selected" not in cached:
        await callback.answer("Кэш не найден.", show_alert=True)
        return

    if idx in cached["selected"]:
        cached["selected"].discard(idx)
        selected = False
    else:
        cached["selected"].add(idx)
        selected = True
    cache.update(video_id)

    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=_idea_kb(video_id, idx, selected))
    except TelegramBadRequest:
        pass
    await _update_summary(callback.bot, video_id)


@router.callback_query(F.data.startswith("save_ideas:"), is_owner_cb)
async def handle_save_ideas(callback: CallbackQuery):
    video_id = callback.data.split(":", 1)[1]
    cached = cache.get(video_id)
    if not cached or "ideas" not in cached:
        await callback.answer("Идеи не найдены в кэше.", show_alert=True)
        return

    selected = cached.get("selected", set())
    if not selected:
        await callback.answer("Ничего не выбрано.", show_alert=True)
        return

    chosen = [cached["ideas"][i] for i in sorted(selected)]
    count = save_ideas(
        ideas=chosen,
        source_url=cached["url"],
        source_title=cached["title"],
        source_channel=cached["channel"],
    )

    await callback.answer(f"Сохранено {count} идей!")

    text = f"✅ Сохранено {count} идей в бэклог"
    try:
        await callback.message.edit_text(text, parse_mode="Markdown")
    except TelegramBadRequest:
        await callback.message.edit_text(text)


@router.callback_query(F.data == "cancel_ideas", is_owner_cb)
async def handle_cancel_ideas(callback: CallbackQuery):
    await callback.answer("Отменено")
    await callback.message.edit_text("🚫 Идеи не сохранены.")


def main():
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    log.info("Bot starting, owner_id=%s, model=%s", settings.telegram_owner_id, settings.openrouter_model)
    asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    main()
