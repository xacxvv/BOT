"""OpenAI-тай холбогдон зөвлөмж гаргах давхарга."""

from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI

from config import BotConfig

logger = logging.getLogger(__name__)


class AIAssistant:
    """OpenAI-г ашиглан 5-8 алхамтай зөвлөмж гаргах туслах класс."""

    def __init__(self, config: BotConfig):
        """API түлхүүрийг авч, OpenAI клиент үүсгэнэ."""

        self.config = config
        if config.openai_api_key:
            self.client = OpenAI(api_key=config.openai_api_key)
        else:
            self.client = None

    def generate_steps(self, issue_type: str, description: str) -> str:
        """Асуудлын тайлбар дээр үндэслэн алхмуудыг үүсгэх."""

        if not self.client:
            # API түлхүүр алга бол хэрэглэгчид ойлгомжтой тайлбар буцаана.
            return (
                "⚠️ OpenAI түлхүүр тохируулаагүй байна. МТ-ийн төвтэй шууд "
                "холбогдоно уу."
            )

        try:
            system_prompt = (
                "You are an IT support assistant for a Mongolian university. "
                "Give concise, practical steps in Mongolian." 
            )
            user_prompt = (
                "Асуудлын төрөл: {issue}\n"
                "Хэрэглэгчийн тайлбар: {desc}\n"
                "5-8 алхамтай, маш практик зөвлөгөө өгнө үү."
            ).format(issue=issue_type, desc=description)

            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content: Optional[str] = response.choices[0].message.content
            return content or "AI-ээс хоосон хариу ирлээ."
        except Exception as exc:  # noqa: BLE001 - анхан шатны жишээ тул ерөнхий алдаа барина
            logger.exception("OpenAI API дуудлагад алдаа гарлаа: %s", exc)
            return (
                "⚠️ OpenAI-д холбогдоход асуудал гарлаа. Та дараа дахин "
                "оролдоно уу эсвэл шууд МТ-ийн төвтэй холбогдоно уу."
            )
