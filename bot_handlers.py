"""Telegram ботын бүх хандалт, ярианы логикийг удирдах модуль.

Энд python-telegram-bot-ийн Handler, ConversationHandler ашиглан хэрэглэгчээс
мэдээлэл авах, OpenAI-с зөвлөгөө авах, өгөгдлийн сантай холбох бүхий л үйлдлийг
багцалж өгч байна.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from enum import Enum, auto
from typing import Any, Dict, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from ai import AIAssistant
from config import BotConfig
from database import Database

logger = logging.getLogger(__name__)


class States(Enum):
    """Ярилцлагын үе шатыг тодорхойлох Enum."""

    AUTH_WAITING_CODE = auto()
    CHOOSING_ISSUE_TYPE = auto()
    TYPING_DESCRIPTION = auto()
    ADD_EMPLOYEE_CODE = auto()
    ADD_EMPLOYEE_LASTNAME = auto()
    ADD_EMPLOYEE_FIRSTNAME = auto()
    ADD_EMPLOYEE_MIDDLENAME = auto()
    ADD_EMPLOYEE_ORG = auto()
    ADD_EMPLOYEE_ROLE = auto()
    REPORT_WAITING_RANGE = auto()


ISSUE_CATEGORIES: Dict[str, Dict[str, str]] = {
    "able_erp": {
        "title": "Able ERP систем",
        "tip": "VPN холболтоо шалгаж, браузераа дахин асаагаарай.",
    },
    "network": {
        "title": "Сүлжээ",
        "tip": "Кабель, Wi-Fi асаалт, IP тохиргоогоо шалгана уу.",
    },
    "software": {
        "title": "Программ хангамж",
        "tip": "Лиценз, шинэчлэлт болон дахин асаалт хийж үзээрэй.",
    },
    "hardware": {
        "title": "Тоног төхөөрөмж",
        "tip": "Цахилгаан, кабель, индикатор гэрлийг шалгана уу.",
    },
    "printer": {
        "title": "Принтер",
        "tip": "Цаас, хор, холболт, default принтер тохиргоогоо шалгаарай.",
    },
    "email": {
        "title": "И-мэйл",
        "tip": "И-мэйл клиентийн серверийн хаяг, нууц үгээ шалгана уу.",
    },
    "other": {"title": "Бусад", "tip": "Асуудлаа тодорхой бичиж илгээнэ үү."},
}


class BotHandler:
    """Telegram ботын handler-уудыг бүлэглэсэн класс."""

    def __init__(self, config: BotConfig, database: Database, ai: AIAssistant):
        self.config = config
        self.db = database
        self.ai = ai

    # ------------------------------------------------
    # Туслах функцууд
    # ------------------------------------------------
    def get_current_employee(self, update: Update) -> Optional[Dict[str, Any]]:
        """Telegram ID-аар одоогийн хэрэглэгчийг олж авах."""

        if update.effective_user is None:
            return None
        telegram_id = update.effective_user.id
        return self.db.get_employee_by_telegram_id(telegram_id)

    def is_head(self, update: Update) -> bool:
        """Эрхлэгч эсэхийг шалгах."""

        emp = self.get_current_employee(update)
        return bool(emp and emp.get("role") == "head")

    def is_engineer(self, update: Update) -> bool:
        """Инженер эсэхийг шалгах."""

        emp = self.get_current_employee(update)
        return bool(emp and emp.get("role") == "engineer")

    # ------------------------------------------------
    # UI бүтээх туслахууд
    # ------------------------------------------------
    def build_issue_keyboard(self) -> ReplyKeyboardMarkup:
        """Асуудлын төрлийн товчтой ReplyKeyboard бэлдэх."""

        buttons = [
            [ISSUE_CATEGORIES["able_erp"]["title"], ISSUE_CATEGORIES["network"]["title"]],
            [ISSUE_CATEGORIES["software"]["title"], ISSUE_CATEGORIES["hardware"]["title"]],
            [ISSUE_CATEGORIES["printer"]["title"], ISSUE_CATEGORIES["email"]["title"]],
            [ISSUE_CATEGORIES["other"]["title"]],
        ]
        return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

    def _title_to_key(self, title: str) -> Optional[str]:
        """Хэрэглэгчийн илгээсэн гарчгийг дотоод түлхүүр рүү хувиргах."""

        for key, data in ISSUE_CATEGORIES.items():
            if data["title"].lower() == title.lower():
                return key
        return None

    def format_employee_name(self, employee: Dict[str, Any]) -> str:
        """Овгийн эхний үсэг + нэр форматаар харуулах."""

        last = employee.get("last_name", "")
        first = employee.get("first_name", "")
        return f"{last[0]}.{first}" if last else first

    # ------------------------------------------------
    # /start командыг хэрэгжүүлэх
    # ------------------------------------------------
    async def start(self, update: Update, context: CallbackContext) -> int:
        """Бот эхлүүлэх үед ажилтны код шалгаж мэндчилэх."""

        employee = self.get_current_employee(update)
        if employee:
            name = self.format_employee_name(employee)
            await update.message.reply_text(
                f"{name} сайн байна уу! Асуудлын төрлөө сонгоно уу.",
                reply_markup=self.build_issue_keyboard(),
            )
            return States.CHOOSING_ISSUE_TYPE

        await update.message.reply_text(
            "Сайн байна уу! Ажилтны кодоо оруулна уу:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return States.AUTH_WAITING_CODE

    async def auth_code(self, update: Update, context: CallbackContext) -> int:
        """Ажилтны код авч баталгаажуулах."""

        code = (update.message.text or "").strip()
        employee = self.db.get_employee_by_code(code)
        if not employee:
            await update.message.reply_text(
                "Ийм ажилтны код бүртгэлгүй байна. Та кодоо зөв шалгаад дахин оруулна уу."
            )
            return States.AUTH_WAITING_CODE

        telegram_id = update.effective_user.id
        self.db.bind_telegram_to_employee(employee["id"], telegram_id)
        name = self.format_employee_name(employee)
        await update.message.reply_text(
            f"{name} сайн байна уу! Та Мэдээлэл технологийн төвтэй холбогдохдоо асуудлын төрлөө сонгоно уу.",
            reply_markup=self.build_issue_keyboard(),
        )
        return States.CHOOSING_ISSUE_TYPE

    # ------------------------------------------------
    # Асуудлын төрөл сонгох алхам
    # ------------------------------------------------
    async def choose_issue(self, update: Update, context: CallbackContext) -> int:
        """Хэрэглэгчийн сонгосон асуудлын төрлийг хадгалах."""

        chosen_title = update.message.text
        key = self._title_to_key(chosen_title)
        if not key:
            await update.message.reply_text(
                "Цэснээс асуудлын төрлөө сонгоно уу.",
                reply_markup=self.build_issue_keyboard(),
            )
            return States.CHOOSING_ISSUE_TYPE

        context.user_data["issue_type"] = key
        tip = ISSUE_CATEGORIES[key]["tip"]
        await update.message.reply_text(
            f"Анхан шатны зөвлөгөө: {tip}\n\nОдоо асуудлынхаа талаар дэлгэрэнгүй тайлбар бичнэ үү:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return States.TYPING_DESCRIPTION

    # ------------------------------------------------
    # Асуудлын дэлгэрэнгүй тайлбарыг авч, AI-с зөвлөгөө авах
    # ------------------------------------------------
    async def receive_description(self, update: Update, context: CallbackContext) -> int:
        """Асуудлын тайлбарыг авч, OpenAI-аас алхамууд үүсгэж илгээх."""

        description = update.message.text
        issue_type = context.user_data.get("issue_type", "other")
        employee = self.get_current_employee(update)
        if not employee:
            await update.message.reply_text("Та эхлээд /start командаар нэвтэрнэ үү.")
            return ConversationHandler.END

        call_id = self.db.create_call(employee["id"], issue_type, description)

        suggestion = self.ai.generate_steps(issue_type, description)
        self.db.update_call_ai_suggestion(call_id, suggestion)

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Тус боллоо ✅", callback_data=f"help_ok_{call_id}"
                    ),
                    InlineKeyboardButton(
                        "Тус болсонгүй ❌", callback_data=f"help_bad_{call_id}"
                    ),
                ]
            ]
        )

        await update.message.reply_text(
            f"🤖 Миний санал болгож буй алхмууд:\n\n{suggestion}",
            reply_markup=keyboard,
        )

        # Ярилцлагыг дуусгавал гол меню рүү буцааж болно. Энд END гэж буцааж, дахин /start ашиглуулна.
        return ConversationHandler.END

    # ------------------------------------------------
    # CallbackQuery дээр AI тус боллоо/болсонгүй-ийг боловсруулах
    # ------------------------------------------------
    async def handle_help_feedback(self, update: Update, context: CallbackContext) -> None:
        """AI зөвлөгөөний үр дүнг тэмдэглэж, шаардлагатай бол инженер рүү шилжүүлэх."""

        query = update.callback_query
        await query.answer()
        data = query.data or ""

        if data.startswith("help_ok_"):
            call_id = int(data.replace("help_ok_", ""))
            self.db.mark_call_ai_helpful(call_id, True)
            self.db.mark_call_resolved(call_id)
            await query.edit_message_text("Танд тус болсонд таатай байна. Амжилт хүсье!")
            return

        if data.startswith("help_bad_"):
            call_id = int(data.replace("help_bad_", ""))
            self.db.mark_call_ai_helpful(call_id, False)
            self.db.mark_call_need_engineer(call_id)
            await query.edit_message_text(
                "Таны хүсэлтийг МТ-ийн төвд шилжүүллээ. Инженерүүд удахгүй холбогдох болно."
            )
            await self.notify_head_need_engineer(call_id, context)
            # 10 минутын дараа автомат оноолт хийх ажлыг бүртгэж байна.
            context.job_queue.run_once(
                self.auto_assign_job, when=timedelta(minutes=10), data={"call_id": call_id}
            )

    async def notify_head_need_engineer(self, call_id: int, context: CallbackContext) -> None:
        """Эрхлэгчид шинэ дуудлагын талаар мэдэгдэл илгээх."""

        head = self.db.get_head_employee(self.config.head_employee_code)
        call = self.db.get_call_by_id(call_id)
        employee = self.db.get_employee_by_id(call["employee_id"]) if call else None

        if head and head.get("telegram_id"):
            text = (
                "⚠️ Шинэ дуудлага AI-аас тус болоогүй тул инженер оноох шаардлагатай байна.\n"
                f"Дуудлагын ID: {call_id}\n"
                f"Асуудлын төрөл: {call['issue_type']}\n"
                f"Тайлбар: {call['description']}\n"
            )
            if employee:
                text += f"Хүсэлт гаргасан: {self.format_employee_name(employee)} ({employee['org_unit']})"
            await context.bot.send_message(head["telegram_id"], text)

    async def auto_assign_job(self, context: CallbackContext) -> None:
        """10 минутын дараа автомат оноолт хийх ажил."""

        job_data = context.job.data or {}
        call_id = job_data.get("call_id")
        if call_id is None:
            return

        call = self.db.get_call_by_id(call_id)
        if not call:
            return
        # Хэрэв статус одоог хүртэл инженер оноогдоогүй хэвээр байвал автоматаар оноох
        if call.get("status") != "need_engineer" or call.get("assigned_engineer_id"):
            return

        engineer = self.db.get_least_loaded_engineer()
        if not engineer:
            return

        self.db.assign_call_to_engineer(call_id, engineer["id"])

        # Инженерт мэдэгдэл илгээх
        if engineer.get("telegram_id"):
            await context.bot.send_message(
                chat_id=engineer["telegram_id"],
                text=(
                    "Танд шинэ дуудлага оноолоо. Дуудлагын ID: "
                    f"{call_id}. Асуудлын төрөл: {call['issue_type']}"
                ),
            )

    # ------------------------------------------------
    # Эрхлэгчийн /add_employee командыг хэрэгжүүлэх яриа
    # ------------------------------------------------
    async def add_employee_start(self, update: Update, context: CallbackContext) -> int:
        """Шинэ ажилтан нэмэх процессыг эхлүүлэх."""

        if not self.is_head(update):
            await update.message.reply_text(
                "Энэ командыг зөвхөн МТ-ийн төвийн эрхлэгч ашиглаж болно."
            )
            return ConversationHandler.END

        await update.message.reply_text("Шинэ ажилтны кодыг оруулна уу:")
        return States.ADD_EMPLOYEE_CODE

    async def add_employee_code(self, update: Update, context: CallbackContext) -> int:
        context.user_data["new_emp_code"] = update.message.text.strip()
        await update.message.reply_text("Овгийг оруулна уу:")
        return States.ADD_EMPLOYEE_LASTNAME

    async def add_employee_lastname(self, update: Update, context: CallbackContext) -> int:
        context.user_data["new_emp_last"] = update.message.text.strip()
        await update.message.reply_text("Нэрийг оруулна уу:")
        return States.ADD_EMPLOYEE_FIRSTNAME

    async def add_employee_firstname(self, update: Update, context: CallbackContext) -> int:
        context.user_data["new_emp_first"] = update.message.text.strip()
        await update.message.reply_text(
            "Дунд нэр / эцгийн нэр байвал оруулна уу, байхгүй бол зүгээр ENTER дарна уу:"
        )
        return States.ADD_EMPLOYEE_MIDDLENAME

    async def add_employee_middlename(self, update: Update, context: CallbackContext) -> int:
        context.user_data["new_emp_middle"] = update.message.text.strip()
        await update.message.reply_text(
            "Бүтцийн нэгжийг оруулна уу (жишээ нь: МТ-ийн төв, Цагдаагийн сургууль гэх мэт):"
        )
        return States.ADD_EMPLOYEE_ORG

    async def add_employee_org(self, update: Update, context: CallbackContext) -> int:
        context.user_data["new_emp_org"] = update.message.text.strip()
        await update.message.reply_text("Роль сонгоно уу (employee / engineer / head):")
        return States.ADD_EMPLOYEE_ROLE

    async def add_employee_role(self, update: Update, context: CallbackContext) -> int:
        role = update.message.text.strip()
        if role not in {"employee", "engineer", "head"}:
            await update.message.reply_text("employee / engineer / head гурваас сонгоно уу.")
            return States.ADD_EMPLOYEE_ROLE

        data = context.user_data
        self.db.add_or_update_employee(
            data.get("new_emp_code"),
            data.get("new_emp_last"),
            data.get("new_emp_first"),
            data.get("new_emp_middle"),
            data.get("new_emp_org"),
            role,
        )
        await update.message.reply_text("Бүртгэл амжилттай хадгалагдлаа.")
        return ConversationHandler.END

    # ------------------------------------------------
    # /report командаар огнооны хооронд статистик гаргах
    # ------------------------------------------------
    async def report_start(self, update: Update, context: CallbackContext) -> int:
        """Эрхлэгчид тайлангийн хугацаа сонгох меню харуулах."""

        if not self.is_head(update):
            await update.message.reply_text(
                "Энэ командыг зөвхөн МТ-ийн төвийн эрхлэгч ашиглаж болно."
            )
            return ConversationHandler.END

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Өнөөдөр", callback_data="report_today")],
                [InlineKeyboardButton("Сүүлийн 7 хоног", callback_data="report_7")],
                [InlineKeyboardButton("Энэ сар", callback_data="report_this_month")],
                [InlineKeyboardButton("Өнгөрсөн сар", callback_data="report_last_month")],
                [InlineKeyboardButton("Хугацаа сонгох", callback_data="report_custom")],
            ]
        )
        await update.message.reply_text("Тайлангийн хугацааг сонгоно уу:", reply_markup=keyboard)
        return States.REPORT_WAITING_RANGE

    async def report_range(self, update: Update, context: CallbackContext) -> int:
        """Inline товчоор сонгосон хугацааг тооцож тайлан гаргах."""

        query = update.callback_query
        await query.answer()
        data = query.data
        today = date.today()

        if data == "report_today":
            start, end = today, today
        elif data == "report_7":
            start, end = today - timedelta(days=7), today
        elif data == "report_this_month":
            start = today.replace(day=1)
            end = today
        elif data == "report_last_month":
            first_this = today.replace(day=1)
            last_month_end = first_this - timedelta(days=1)
            start = last_month_end.replace(day=1)
            end = last_month_end
        elif data == "report_custom":
            await query.edit_message_text(
                "Хоёр огноог YYYY-MM-DD YYYY-MM-DD хэлбэрээр бичнэ үү (эхлэл, төгсгөл):"
            )
            return States.REPORT_WAITING_RANGE
        else:
            await query.edit_message_text("Тодорхойгүй сонголт.")
            return ConversationHandler.END

        report_text = self._build_report_text(start, end)
        await query.edit_message_text(report_text)
        return ConversationHandler.END

    async def report_custom_range(self, update: Update, context: CallbackContext) -> int:
        """Хэрэглэгчийн бичсэн хоёр огноог уншиж тайлан гаргах."""

        parts = (update.message.text or "").split()
        if len(parts) != 2:
            await update.message.reply_text("Жишээ: 2025-01-01 2025-01-31 гэж бичнэ үү.")
            return States.REPORT_WAITING_RANGE

        try:
            start = date.fromisoformat(parts[0])
            end = date.fromisoformat(parts[1])
        except ValueError:
            await update.message.reply_text("Огнооны формат буруу байна.")
            return States.REPORT_WAITING_RANGE

        report_text = self._build_report_text(start, end)
        await update.message.reply_text(report_text)
        return ConversationHandler.END

    def _build_report_text(self, start: date, end: date) -> str:
        """DB-гээс статистик авч текст болгон форматлах."""

        stats = self.db.get_calls_stats(start, end)
        lines = [f"📊 Тайлан: {start} – {end}", f"Нийт дуудлага: {stats['total']}"]

        lines.append("\nБүтцийн нэгжээр:")
        if stats["by_org"]:
            for org, cnt in stats["by_org"].items():
                lines.append(f"- {org}: {cnt}")
        else:
            lines.append("- Мэдээлэл байхгүй")

        lines.append("\nАсуудлын төрлөөр:")
        if stats["by_issue"]:
            for issue, cnt in stats["by_issue"].items():
                title = ISSUE_CATEGORIES.get(issue, {}).get("title", issue)
                lines.append(f"- {title}: {cnt}")
        else:
            lines.append("- Мэдээлэл байхгүй")

        lines.append("\nТөлөвөөр:")
        if stats["by_status"]:
            for status, cnt in stats["by_status"].items():
                lines.append(f"- {status}: {cnt}")
        else:
            lines.append("- Мэдээлэл байхгүй")

        return "\n".join(lines)

    # ------------------------------------------------
    # /assign_call CALL_ID ENGINEER_CODE командыг хэрэгжүүлэх
    # ------------------------------------------------
    async def assign_call(self, update: Update, context: CallbackContext) -> None:
        """Эрхлэгч тодорхой дуудлагыг инженерт оноох."""

        if not self.is_head(update):
            await update.message.reply_text(
                "Энэ командыг зөвхөн МТ-ийн төвийн эрхлэгч ашиглаж болно."
            )
            return

        parts = (update.message.text or "").split()
        if len(parts) != 3:
            await update.message.reply_text("Жишээ: /assign_call 15 ITENG002")
            return

        _, call_str, engineer_code = parts
        try:
            call_id = int(call_str)
        except ValueError:
            await update.message.reply_text("Дуудлагын ID тоо байх ёстой.")
            return

        call = self.db.get_call_by_id(call_id)
        if not call:
            await update.message.reply_text("Ийм дуудлага олдсонгүй.")
            return

        engineer = self.db.get_employee_by_code(engineer_code)
        if not engineer or engineer.get("role") != "engineer":
            await update.message.reply_text("Инженерийн код буруу байна.")
            return

        self.db.assign_call_to_engineer(call_id, engineer["id"])
        if engineer.get("telegram_id"):
            await context.bot.send_message(
                engineer["telegram_id"],
                f"Танд шинэ дуудлага оноолоо. ID: {call_id}",
            )

        await update.message.reply_text(
            f"Дуудлага {call_id}-г {self.format_employee_name(engineer)}-д амжилттай оноолоо."
        )

# ------------------------------------------------
# Handler-уудыг Application-д бүртгэх туслах функц
# ------------------------------------------------
def register_handlers(application: Application, handler: BotHandler) -> None:
    """Бүх Command болон Conversation handler-ийг бүртгэх."""

    conv_auth = ConversationHandler(
        entry_points=[CommandHandler("start", handler.start)],
        states={
            States.AUTH_WAITING_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.auth_code)
            ],
            States.CHOOSING_ISSUE_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.choose_issue)
            ],
            States.TYPING_DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handler.receive_description
                )
            ],
        },
        fallbacks=[],
    )

    conv_add_employee = ConversationHandler(
        entry_points=[CommandHandler("add_employee", handler.add_employee_start)],
        states={
            States.ADD_EMPLOYEE_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.add_employee_code)
            ],
            States.ADD_EMPLOYEE_LASTNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handler.add_employee_lastname
                )
            ],
            States.ADD_EMPLOYEE_FIRSTNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handler.add_employee_firstname
                )
            ],
            States.ADD_EMPLOYEE_MIDDLENAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handler.add_employee_middlename
                )
            ],
            States.ADD_EMPLOYEE_ORG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.add_employee_org)
            ],
            States.ADD_EMPLOYEE_ROLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.add_employee_role)
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )

    conv_report = ConversationHandler(
        entry_points=[CommandHandler("report", handler.report_start)],
        states={
            States.REPORT_WAITING_RANGE: [
                CallbackQueryHandler(handler.report_range),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handler.report_custom_range),
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )

    application.add_handler(conv_auth)
    application.add_handler(conv_add_employee)
    application.add_handler(conv_report)
    application.add_handler(CommandHandler("assign_call", handler.assign_call))
    application.add_handler(CallbackQueryHandler(handler.handle_help_feedback))
