"""МТ төвийн ботын тохиргоог хадгалах модуль.

Энд бот ажиллахад шаардлагатай токен, түлхүүрүүдийг Dataclass хэлбэрээр
тодорхойлж, орчноос унших туслах функц бичнэ."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class BotConfig:
    """Ботын бүх тохиргоог нэг дор хадгалах Dataclass.

    - telegram_token: Telegram ботоо ажиллуулах нууц токен.
    - openai_api_key: OpenAI-ийн API түлхүүр.
    - head_employee_code: МТ төвийн эрхлэгчийн ажилтны код.
    - db_path: SQLite өгөгдлийн сангийн файл байрлал.
    """

    telegram_token: str
    openai_api_key: str
    head_employee_code: str
    db_path: str = "bot.db"


def load_config_from_env() -> BotConfig:
    """Орчны хувьсагчаас тохиргоо унших туслах функц.

    Энд хэрэглэгчид .env файл эсвэл терминал дээр дараах тушаалаар
    тохиргоогоо өгөх боломжтой:
    - Linux/macOS: ``export TELEGRAM_TOKEN="..."``
      ``export OPENAI_API_KEY="..."``
    - Windows (PowerShell): ``$Env:TELEGRAM_TOKEN="..."``
      ``$Env:OPENAI_API_KEY="..."``

    Ийнхүү нууц мэдээллийг кодонд хатуу бичихгүй байх нь аюулгүй байдлыг
    хангаж, репод ил гарахаас сэргийлнэ.
    """

    telegram_token = os.getenv("TELEGRAM_TOKEN", "")
    openai_api_key = os.getenv("OPENAI_API_KEY", "")

    # МТ төвийн эрхлэгчийн ажилтны кодыг жишээгээр хатуу бичиж өгч байна.
    head_employee_code = "ITC001"

    return BotConfig(
        telegram_token=telegram_token,
        openai_api_key=openai_api_key,
        head_employee_code=head_employee_code,
        db_path="bot.db",
    )
