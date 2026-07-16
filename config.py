"""Конфигурация бота — читается из переменных окружения / .env файла."""
import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name}. "
            f"Скопируйте .env.example в .env и заполните значения."
        )
    return value


BOT_TOKEN = _require("BOT_TOKEN")
ADMIN_GROUP_ID = int(_require("ADMIN_GROUP_ID"))

WELCOME_TEXT = os.getenv(
    "WELCOME_TEXT",
    "Напишите, какой именно товар вас интересует (можете добавить ссылку или скрин) 
    Совсем скоро мы с вами свяжемся и ответим на все вопросы!",
)
AUTO_REPLY_TEXT = os.getenv(
    "AUTO_REPLY_TEXT",
    "Спасибо за обращение! Мы вернёмся к вам, как только сможем 🤝",
)
DB_PATH = os.getenv("DB_PATH", "bot.db")
