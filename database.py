"""SQLite өгөгдлийн сантай ажиллах анги.

Энд шаардлагатай хүснэгтүүдийг үүсгэж, ботын бүх CRUD үйлдлүүдийг
хялбар аргаар гүйцэтгэх функцуудыг бичнэ."""

from __future__ import annotations

import sqlite3
from datetime import datetime, date
from typing import Any, Dict, List, Optional


class Database:
    """SQLite өгөгдлийн санг удирдах энгийн класс."""

    def __init__(self, db_path: str):
        """Анхдагч байгуулагч.

        - SQLite файлд холбогдож, байхгүй бол шинэ файл үүсгэнэ.
        - Хэрэглэх шаардлагатай хүснэгтүүдийг нэг удаа үүсгэж өгнө.
        """

        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        """Хэрэглэгдэх бүх хүснэгтийг үүсгэнэ."""

        cursor = self.connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT UNIQUE NOT NULL,
                last_name TEXT NOT NULL,
                first_name TEXT NOT NULL,
                middle_name TEXT,
                org_unit TEXT NOT NULL,
                role TEXT NOT NULL,
                telegram_id INTEGER
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                issue_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                openai_suggestion TEXT,
                is_ai_helpful INTEGER,
                assigned_engineer_id INTEGER,
                resolved_at TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (assigned_engineer_id) REFERENCES employees(id)
            )
            """
        )

        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status)"""
        )

        self.connection.commit()

    # -----------------------------
    # Ажилтны мэдээлэлтэй холбоотой функцууд
    # -----------------------------
    def _row_to_dict(self, row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        """SQLite Row объектуудыг dict болгож хөрвүүлэх жижиг туслах."""

        if row is None:
            return None
        return dict(row)

    def get_employee_by_code(self, employee_code: str) -> Optional[Dict[str, Any]]:
        """Ажилтны кодоор мэдээллийг хайх."""

        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM employees WHERE employee_code = ?", (employee_code,)
        )
        return self._row_to_dict(cursor.fetchone())

    def get_employee_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Telegram ID-аар ажилтныг хайх."""

        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM employees WHERE telegram_id = ?", (telegram_id,))
        return self._row_to_dict(cursor.fetchone())

    def bind_telegram_to_employee(self, employee_id: int, telegram_id: int) -> None:
        """Ажилтны бүртгэлд Telegram ID-г холбох."""

        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE employees SET telegram_id = ? WHERE id = ?",
            (telegram_id, employee_id),
        )
        self.connection.commit()

    def add_or_update_employee(
        self,
        employee_code: str,
        last_name: str,
        first_name: str,
        middle_name: Optional[str],
        org_unit: str,
        role: str,
    ) -> None:
        """Шинэ ажилтан нэмэх эсвэл байгаа мэдээллийг шинэчлэх."""

        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO employees (employee_code, last_name, first_name, middle_name, org_unit, role)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_code) DO UPDATE SET
                last_name=excluded.last_name,
                first_name=excluded.first_name,
                middle_name=excluded.middle_name,
                org_unit=excluded.org_unit,
                role=excluded.role
            """,
            (employee_code, last_name, first_name, middle_name, org_unit, role),
        )
        self.connection.commit()

    # -----------------------------
    # Дуудлагатай холбоотой функцууд
    # -----------------------------
    def create_call(self, employee_id: int, issue_type: str, description: str) -> int:
        """Шинэ дуудлага үүсгэж ID-г буцаана."""

        cursor = self.connection.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT INTO calls (employee_id, issue_type, description, created_at, status)
            VALUES (?, ?, ?, ?, 'new')
            """,
            (employee_id, issue_type, description, created_at),
        )
        self.connection.commit()
        return cursor.lastrowid

    def update_call_ai_suggestion(self, call_id: int, suggestion: str) -> None:
        """AI-ийн зөвлөмж болон төлөвийг хадгалах."""

        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE calls SET openai_suggestion = ?, status = 'ai_suggested' WHERE id = ?",
            (suggestion, call_id),
        )
        self.connection.commit()

    def mark_call_ai_helpful(self, call_id: int, helpful: bool) -> None:
        """AI зөвлөгөө тус болсон эсэхийг тэмдэглэх."""

        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE calls SET is_ai_helpful = ? WHERE id = ?",
            (1 if helpful else 0, call_id),
        )
        self.connection.commit()

    def mark_call_need_engineer(self, call_id: int) -> None:
        """Инженер шаардлагатай гэж тэмдэглэж статус өөрчлөх."""

        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE calls SET status = 'need_engineer' WHERE id = ?", (call_id,)
        )
        self.connection.commit()

    def assign_call_to_engineer(self, call_id: int, engineer_id: int) -> None:
        """Дуудлагыг тодорхой инженерт оноох."""

        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE calls SET assigned_engineer_id = ?, status = 'assigned' WHERE id = ?",
            (engineer_id, call_id),
        )
        self.connection.commit()

    def mark_call_resolved(self, call_id: int) -> None:
        """Дуудлага шийдэгдсэн болохыг тэмдэглэх."""

        cursor = self.connection.cursor()
        resolved_at = datetime.utcnow().isoformat()
        cursor.execute(
            "UPDATE calls SET status = 'resolved', resolved_at = ? WHERE id = ?",
            (resolved_at, call_id),
        )
        self.connection.commit()

    def get_call_by_id(self, call_id: int) -> Optional[Dict[str, Any]]:
        """ID-аар дуудлагын мэдээлэл авах."""

        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM calls WHERE id = ?", (call_id,))
        return self._row_to_dict(cursor.fetchone())

    def get_head_employee(self, head_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Эрхлэгчийн мэдээллийг авах (код эсвэл role-оор)."""

        cursor = self.connection.cursor()
        if head_code:
            cursor.execute(
                "SELECT * FROM employees WHERE employee_code = ?", (head_code,)
            )
        else:
            cursor.execute("SELECT * FROM employees WHERE role = 'head' LIMIT 1")
        return self._row_to_dict(cursor.fetchone())

    def get_employee_by_id(self, employee_id: int) -> Optional[Dict[str, Any]]:
        """ID утгаар ажилтны бүртгэлийг буцаах."""

        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
        return self._row_to_dict(cursor.fetchone())

    def get_engineers(self) -> List[Dict[str, Any]]:
        """Бүх инженерүүдийн жагсаалтыг буцаах."""

        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM employees WHERE role = 'engineer'")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_least_loaded_engineer(self) -> Optional[Dict[str, Any]]:
        """Одоо хамгийн цөөн дуудлагатай инженерыг сонгох.

        Статус нь 'need_engineer' эсвэл 'assigned' байгаа дуудлагыг тоолж,
        хамгийн бага тоотой инженерыг буцаана.
        """

        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT e.*, COUNT(c.id) AS workload
            FROM employees e
            LEFT JOIN calls c ON e.id = c.assigned_engineer_id AND c.status IN ('need_engineer', 'assigned')
            WHERE e.role = 'engineer'
            GROUP BY e.id
            ORDER BY workload ASC
            LIMIT 1
            """
        )
        return self._row_to_dict(cursor.fetchone())

    # -----------------------------
    # Тайлангийн функцууд
    # -----------------------------
    def get_calls_stats(self, start_date: date, end_date: date) -> Dict[str, Any]:
        """Өгөгдсөн огнооны хоорондхи дуудлагын статистик гаргах."""

        cursor = self.connection.cursor()
        start_str = datetime.combine(start_date, datetime.min.time()).isoformat()
        end_str = datetime.combine(end_date, datetime.max.time()).isoformat()

        # Нийт дуудлага
        cursor.execute(
            "SELECT COUNT(*) AS total FROM calls WHERE created_at BETWEEN ? AND ?",
            (start_str, end_str),
        )
        total = cursor.fetchone()[0]

        # Бүтцийн нэгжээр бүлэглэх
        cursor.execute(
            """
            SELECT emp.org_unit, COUNT(c.id) AS cnt
            FROM calls c
            JOIN employees emp ON c.employee_id = emp.id
            WHERE c.created_at BETWEEN ? AND ?
            GROUP BY emp.org_unit
            """,
            (start_str, end_str),
        )
        by_org = {row[0]: row[1] for row in cursor.fetchall()}

        # Асуудлын төрлөөр бүлэглэх
        cursor.execute(
            """
            SELECT issue_type, COUNT(id) AS cnt
            FROM calls
            WHERE created_at BETWEEN ? AND ?
            GROUP BY issue_type
            """,
            (start_str, end_str),
        )
        by_issue = {row[0]: row[1] for row in cursor.fetchall()}

        # Статусаар бүлэглэх
        cursor.execute(
            """
            SELECT status, COUNT(id) AS cnt
            FROM calls
            WHERE created_at BETWEEN ? AND ?
            GROUP BY status
            """,
            (start_str, end_str),
        )
        by_status = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "total": total,
            "by_org": by_org,
            "by_issue": by_issue,
            "by_status": by_status,
        }

    def close(self) -> None:
        """Холболтыг аюулгүй хаах."""

        self.connection.close()
