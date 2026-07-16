"""
Telegram-бот для Take Shot (takeshotbasket.ru).

Как это работает:
1. Клиент жмёт кнопку на сайте -> открывается бот -> видит приветствие.
2. Клиент пишет, какой товар хочет (текст и/или фото/скриншот).
   Бот заводит для клиента ОТДЕЛЬНУЮ ТЕМУ (topic) в группе менеджеров
   и пересылает туда сообщение. Клиенту приходит автоответ.
3. Менеджер просто пишет ответ ПРЯМО В ТЕМЕ клиента — бот доставляет
   этот ответ клиенту от имени бота. Так один менеджер спокойно ведёт
   много диалогов, не путаясь: каждый клиент = своя тема.

Настройка — через .env (см. .env.example и README.md).
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

import config
from storage import Storage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("takeshot_bot")

bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),
)
dp = Dispatcher()
db = Storage(config.DB_PATH)


def _display_name(message: Message) -> str:
    user = message.from_user
    name = user.full_name or "Клиент"
    if user.username:
        name += f" (@{user.username})"
    return name


async def _create_topic(user_id: int, message: Message) -> int:
    """Создаёт тему для клиента, пишет в неё «шапку» и сохраняет связку."""
    user = message.from_user
    title = _display_name(message)[:120]
    topic = await bot.create_forum_topic(
        chat_id=config.ADMIN_GROUP_ID, name=title
    )
    thread_id = topic.message_thread_id
    db.link(
        user_id=user_id,
        thread_id=thread_id,
        username=user.username or "",
        full_name=user.full_name or "",
    )

    header = (
        f"🆕 <b>Новый клиент</b>\n"
        f"Имя: <a href=\"tg://user?id={user.id}\">{user.full_name}</a>\n"
        f"Username: {('@' + user.username) if user.username else '—'}\n"
        f"ID: <code>{user.id}</code>\n\n"
        f"✍️ Просто пишите ответ в этой теме — он уйдёт клиенту от имени бота."
    )
    await bot.send_message(
        config.ADMIN_GROUP_ID, header, message_thread_id=thread_id
    )
    return thread_id


async def _get_or_create_thread(user_id: int, message: Message) -> int:
    thread_id = db.thread_by_user(user_id)
    if thread_id is None:
        return await _create_topic(user_id, message)
    return thread_id


# ---------------------------------------------------------------------------
#  СТОРОНА КЛИЕНТА (личка с ботом)
# ---------------------------------------------------------------------------

@dp.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def on_start(message: Message) -> None:
    await message.answer(config.WELCOME_TEXT)


@dp.message(F.chat.type == ChatType.PRIVATE)
async def on_client_message(message: Message) -> None:
    """Любое сообщение клиента (текст, фото, документ и т.д.)."""
    user_id = message.from_user.id

    is_new = db.thread_by_user(user_id) is None
    thread_id = await _get_or_create_thread(user_id, message)

    try:
        await bot.copy_message(
            chat_id=config.ADMIN_GROUP_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            message_thread_id=thread_id,
        )
    except TelegramBadRequest as e:
        # Тему могли удалить вручную — заводим новую и пробуем ещё раз.
        if "thread not found" in str(e).lower() or "TOPIC_DELETED" in str(e):
            db.forget_thread(thread_id)
            thread_id = await _create_topic(user_id, message)
            await bot.copy_message(
                chat_id=config.ADMIN_GROUP_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=thread_id,
            )
        else:
            raise

    # Автоответ отправляем только при первом обращении, чтобы не спамить.
    if is_new:
        await message.answer(config.AUTO_REPLY_TEXT)


# ---------------------------------------------------------------------------
#  СТОРОНА МЕНЕДЖЕРА (группа с темами)
# ---------------------------------------------------------------------------

@dp.message(
    Command("close"),
    F.chat.id == config.ADMIN_GROUP_ID,
)
async def on_close(message: Message) -> None:
    """/close в теме — закрыть тему и забыть связку."""
    thread_id = message.message_thread_id
    if not thread_id:
        return
    db.forget_thread(thread_id)
    try:
        await bot.close_forum_topic(config.ADMIN_GROUP_ID, thread_id)
    except TelegramBadRequest:
        pass
    await message.reply("Тема закрыта. Новое сообщение клиента заведёт новую тему.")


@dp.message(F.chat.id == config.ADMIN_GROUP_ID)
async def on_manager_message(message: Message) -> None:
    """Ответ менеджера в теме -> доставляем клиенту."""
    # Игнорируем сообщения самого бота (шапки, копии) и сервисные события.
    if message.from_user and message.from_user.id == bot.id:
        return
    if not message.message_thread_id:
        return  # сообщение в «General», а не в теме клиента

    user_id = db.user_by_thread(message.message_thread_id)
    if user_id is None:
        return  # тема не привязана к клиенту

    try:
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=config.ADMIN_GROUP_ID,
            message_id=message.message_id,
        )
    except TelegramBadRequest as e:
        await message.reply(f"❌ Не удалось доставить клиенту: {e}")


# ---------------------------------------------------------------------------

async def main() -> None:
    me = await bot.get_me()
    log.info("Бот @%s запущен. Группа заявок: %s", me.username, config.ADMIN_GROUP_ID)
    try:
        await dp.start_polling(bot)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
