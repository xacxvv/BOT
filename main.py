"""Энгийн заавар:
1. ``python -m venv venv``
2. Linux/macOS: ``source venv/bin/activate``
   Windows: ``venv\\Scripts\\activate``
3. ``pip install python-telegram-bot==20.7 openai``
4. Орчны хувьсагч тохируулах:
   - Linux/macOS: ``export TELEGRAM_TOKEN="..."``
   - Windows (PowerShell): ``$Env:TELEGRAM_TOKEN="..."``
   - OpenAI: ``export OPENAI_API_KEY="..."``
5. ``python main.py`` гэж ажиллуулахад бот асна.

Эдгээр алхмуудыг дагавал МТ-ийн төвийн ажилтан ботоо ажиллуулж чадна."""

from __future__ import annotations

import logging

from telegram.ext import Application

from ai import AIAssistant
from bot_handlers import BotHandler, register_handlers
from config import load_config_from_env
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Ботын гол урсгал: тохиргоо унших, обьектууд үүсгэх, bot run_polling."""

    config = load_config_from_env()
    db = Database(config.db_path)
    ai = AIAssistant(config)
    handler = BotHandler(config, db, ai)

    application = Application.builder().token(config.telegram_token).build()

    register_handlers(application, handler)

    logger.info("Бот ажиллаж эхлэх гэж байна...")
    application.run_polling()


if __name__ == "__main__":
    main()
