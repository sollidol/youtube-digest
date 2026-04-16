import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .config import settings
from .ideas import save_ideas
from .llm import analyze
from .metadata import fetch_video_meta
from .transcript import extract_video_id, fetch_transcript

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

router = Router()

TG_LIMIT = 4096

_digest_cache: dict[str, dict] = {}


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


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_owner(message):
        return
    await message.answer(
        "Кидай ссылку на YouTube — получишь идеи для бизнеса.\n\n"
        f"Модель: `{settings.openrouter_model}`",
        parse_mode="Markdown",
    )


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
    except Exception as e:
        log.error("LLM failed: %s", e)
        await status.edit_text("❌ Ошибка LLM. Попробуй ещё раз.")
        return

    ideas = result.get("ideas", [])
    url = f"https://www.youtube.com/watch?v={video_id}"

    if not ideas:
        await status.edit_text(
            f"📹 {meta['title']}\n🎙 {meta['channel']}\n\n"
            "🤷 Применимых идей не нашлось — видео общеобразовательное."
        )
        return

    _digest_cache[video_id] = {
        "ideas": ideas,
        "title": meta["title"],
        "channel": meta["channel"],
        "url": url,
        "selected": set(range(len(ideas))),
    }

    header = f"📹 {meta['title']}\n🎙 {meta['channel']}\n\n💡 *Идеи ({len(ideas)}):*\n\n"
    ideas_text = ""
    for i, idea in enumerate(ideas):
        tags = ", ".join(f"#{t}" for t in idea.get("tags", []))
        ideas_text += f"✅ *{i + 1}. {idea['title']}*\n{idea['description']}\n_{tags}_\n\n"

    kb = _build_ideas_keyboard(video_id)
    await _safe_send(status, header + ideas_text, edit=True, reply_markup=kb)


def _build_ideas_keyboard(video_id: str) -> InlineKeyboardMarkup:
    cached = _digest_cache[video_id]
    ideas = cached["ideas"]
    selected = cached["selected"]

    buttons = []
    row = []
    for i in range(len(ideas)):
        mark = "✅" if i in selected else "⬜"
        row.append(InlineKeyboardButton(
            text=f"{mark} {i + 1}",
            callback_data=f"toggle:{video_id}:{i}",
        ))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    action_row = []
    if selected:
        label = f"💾 Сохранить ({len(selected)})" if len(selected) < len(ideas) else "💾 Сохранить все"
        action_row.append(InlineKeyboardButton(text=label, callback_data=f"save_ideas:{video_id}"))
    action_row.append(InlineKeyboardButton(text="❌ Не сохранять", callback_data="cancel_ideas"))
    buttons.append(action_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("toggle:"), is_owner_cb)
async def handle_toggle_idea(callback: CallbackQuery):
    _, video_id, idx_str = callback.data.split(":", 2)
    idx = int(idx_str)
    cached = _digest_cache.get(video_id)
    if not cached or "selected" not in cached:
        await callback.answer("Кэш не найден.", show_alert=True)
        return

    if idx in cached["selected"]:
        cached["selected"].discard(idx)
    else:
        cached["selected"].add(idx)

    await callback.answer()
    kb = _build_ideas_keyboard(video_id)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("save_ideas:"), is_owner_cb)
async def handle_save_ideas(callback: CallbackQuery):
    video_id = callback.data.split(":", 1)[1]
    cached = _digest_cache.get(video_id)
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
