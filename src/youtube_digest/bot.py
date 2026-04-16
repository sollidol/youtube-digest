import asyncio
import json
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .config import settings
from .ideas import extract_ideas, save_idea
from .llm import summarize
from .metadata import fetch_video_meta
from .storage import save_digest
from .transcript import extract_video_id, fetch_transcript

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

router = Router()

# video_id -> {summary, title, channel, url}
_digest_cache: dict[str, dict] = {}


def is_owner(message: Message) -> bool:
    return message.from_user and message.from_user.id == settings.telegram_owner_id


def is_owner_cb(callback: CallbackQuery) -> bool:
    return callback.from_user and callback.from_user.id == settings.telegram_owner_id


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_owner(message):
        return
    await message.answer(
        "Кидай ссылку на YouTube — получишь саммари за 30 секунд.\n\n"
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

    await status.edit_text("🧠 Анализирую...")

    meta = await fetch_video_meta(video_id)

    try:
        summary = await summarize(transcript, meta["title"], meta["channel"])
    except Exception as e:
        log.error("LLM failed: %s", e)
        await status.edit_text("❌ Ошибка LLM. Попробуй ещё раз.")
        return

    url = f"https://www.youtube.com/watch?v={video_id}"
    _digest_cache[video_id] = {
        "summary": summary,
        "title": meta["title"],
        "channel": meta["channel"],
        "url": url,
    }

    path = save_digest(video_id, meta["title"], meta["channel"], summary)
    log.info("Saved digest: %s", path)

    header = f"📹 {meta['title']}\n🎙 {meta['channel']}\n\n"
    text = header + summary

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 Извлечь идеи в бэклог", callback_data=f"ideas:{video_id}")]
    ])

    try:
        await status.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    except TelegramBadRequest:
        await status.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("ideas:"), is_owner_cb)
async def handle_ideas_extract(callback: CallbackQuery):
    video_id = callback.data.split(":", 1)[1]
    cached = _digest_cache.get(video_id)
    if not cached:
        await callback.answer("Саммари не найдено в кэше. Кинь ссылку ещё раз.", show_alert=True)
        return

    await callback.answer("Извлекаю идеи...")
    msg = await callback.message.answer("🧠 Извлекаю применимые идеи...")

    try:
        ideas = await extract_ideas(cached["summary"], cached["title"], cached["channel"])
    except Exception as e:
        log.error("Ideas extraction failed: %s", e)
        await msg.edit_text("❌ Не удалось извлечь идеи. Попробуй ещё раз.")
        return

    if not ideas:
        await msg.edit_text("🤷 Применимых идей не нашлось — видео общеобразовательное.")
        return

    _digest_cache[video_id]["ideas"] = ideas
    _digest_cache[video_id]["selected"] = set(range(len(ideas)))

    await _render_ideas_picker(msg, video_id, edit=True)


async def _render_ideas_picker(msg, video_id: str, edit: bool = True):
    cached = _digest_cache[video_id]
    ideas = cached["ideas"]
    selected = cached["selected"]

    lines = [f"💡 *Идей: {len(ideas)} | выбрано: {len(selected)}*\n"]
    for i, idea in enumerate(ideas):
        mark = "✅" if i in selected else "⬜"
        tags = ", ".join(f"#{t}" for t in idea.get("tags", []))
        lines.append(f"{mark} *{i + 1}. {idea['title']}*")
        lines.append(f"{idea['description']}")
        lines.append(f"_{tags}_\n")

    draft = "\n".join(lines)

    buttons = []
    row = []
    for i, idea in enumerate(ideas):
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
    action_row.append(InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel_ideas"))
    buttons.append(action_row)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if edit:
        try:
            await msg.edit_text(draft, parse_mode="Markdown", reply_markup=kb)
        except TelegramBadRequest:
            await msg.edit_text(draft, reply_markup=kb)
    else:
        try:
            await msg.answer(draft, parse_mode="Markdown", reply_markup=kb)
        except TelegramBadRequest:
            await msg.answer(draft, reply_markup=kb)


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
    await _render_ideas_picker(callback.message, video_id, edit=True)


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

    saved = []
    for i in sorted(selected):
        idea = cached["ideas"][i]
        path = save_idea(
            title=idea["title"],
            description=idea["description"],
            tags=idea.get("tags", []),
            source_url=cached["url"],
            source_title=cached["title"],
            source_channel=cached["channel"],
        )
        saved.append(path.name)

    await callback.answer(f"Сохранено {len(saved)} идей!")

    text = f"✅ Сохранено {len(saved)} идей в бэклог:\n"
    for name in saved:
        text += f"• `{name}`\n"

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
