"""Context builder for the in-app AI assistant."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

from database import get_connection
from modules.ai_data_assistant import AccountingDataAssistant


AGENT_MODES = {
    "ask": "Ask",
    "data": "Data",
    "plan": "Plan",
    "fix": "Fix",
    "review": "Review",
}


@dataclass
class AppContextSnapshot:
    screen: str = ""
    user_role: str = ""
    company: str = ""
    notes: str = ""


class AIContextBuilder:
    """Build focused prompts similar to how IDE assistants attach context."""

    BASE_RULES = (
        "Ban la tro ly AI trong phan mem ke toan/xay dung FasTrack ERP.\n"
        "Tra loi bang tieng Viet, ngan gon, uu tien hanh dong cu the.\n"
        "Khong tu y sua/xoa du lieu. Neu can thay doi du lieu, hay neu ro buoc kiem tra va xin xac nhan.\n"
        "Neu cau hoi lien quan quy dinh thue/phap ly, hay nhac nguoi dung kiem tra lai voi van ban moi nhat/chuyen gia.\n"
    )

    MENTION_MAP = {
        "#schema": "schema",
        "#expenses": "expenses",
        "#projects": "projects",
        "#inventory": "inventory",
        "#documents": "documents",
        "#contracts": "contracts",
    }

    MODE_INSTRUCTIONS = {
        "ask": "Che do Ask: giai thich, huong dan thao tac, tra loi nhu mot tro ly san pham.",
        "data": "Che do Data: uu tien phan tich so lieu, neu cong thuc/cach loc, canh bao du lieu bat thuong.",
        "plan": "Che do Plan: chia viec thanh cac buoc nho, neu rui ro, thu tu thuc hien va cach kiem tra.",
        "fix": "Che do Fix: chan doan loi phan mem, de xuat cach sua an toan, khong dua ban va lon khi thieu ngu canh.",
        "review": "Che do Review: uu tien phat hien loi, hoi quy, thieu test, va rui ro van hanh.",
    }

    def __init__(self, snapshot_provider: Optional[Callable[[], Dict]] = None):
        self.snapshot_provider = snapshot_provider

    def build_prompt(self, user_message: str, mode: str = "ask") -> str:
        mode = self._mode_from_message(user_message, mode)
        mentions = self._mentions(user_message)
        sections = [
            self.BASE_RULES,
            self.MODE_INSTRUCTIONS.get(mode, self.MODE_INSTRUCTIONS["ask"]),
            self._snapshot_context(),
        ]
        for mention in mentions:
            sections.append(self._mention_context(mention))
        if not mentions and mode in ("data", "review"):
            sections.append(self._mention_context("schema"))
        sections.append(f"Yeu cau nguoi dung:\n{user_message.strip()}")
        return "\n\n".join(section for section in sections if section)

    def context_labels(self, message: str = "", mode: str = "ask") -> List[str]:
        labels = ["active-screen", AGENT_MODES.get(mode, "Ask")]
        labels.extend(self._mentions(message))
        if mode in ("data", "review") and "schema" not in labels:
            labels.append("schema")
        return labels

    def _mode_from_message(self, message: str, fallback: str) -> str:
        text = message.strip().lower()
        slash_map = {
            "/data": "data",
            "/plan": "plan",
            "/fix": "fix",
            "/review": "review",
            "/ask": "ask",
        }
        for prefix, mode in slash_map.items():
            if text.startswith(prefix):
                return mode
        return fallback if fallback in AGENT_MODES else "ask"

    def _mentions(self, message: str) -> List[str]:
        found = []
        lowered = message.lower()
        for token, key in self.MENTION_MAP.items():
            if token in lowered and key not in found:
                found.append(key)
        return found

    def _snapshot_context(self) -> str:
        data = {}
        if self.snapshot_provider:
            try:
                data = self.snapshot_provider() or {}
            except Exception:
                data = {}
        bits = []
        if data.get("screen"):
            bits.append(f"Man hinh hien tai: {data['screen']}")
        if data.get("user_role"):
            bits.append(f"Vai tro nguoi dung: {data['user_role']}")
        if data.get("company"):
            bits.append(f"Don vi: {data['company']}")
        if data.get("notes"):
            bits.append(f"Ghi chu ngu canh: {data['notes']}")
        return "Ngu canh ung dung:\n" + "\n".join(f"- {bit}" for bit in bits) if bits else ""

    def _mention_context(self, key: str) -> str:
        if key == "schema":
            return "Schema doc duoc phep:\n" + AccountingDataAssistant.SCHEMA_CONTEXT.strip()
        table_groups = {
            "expenses": ("expenses", "expense_categories"),
            "projects": ("projects", "construction_work_items"),
            "inventory": ("materials", "inventory_transactions"),
            "documents": ("documents",),
            "contracts": ("project_contracts", "contract_billings", "project_revenues"),
        }
        tables = table_groups.get(key)
        if not tables:
            return ""
        return f"Ngu canh #{key}:\n" + self._table_sample(tables)

    def _table_sample(self, tables: Iterable[str]) -> str:
        lines: List[str] = []
        try:
            conn = get_connection()
            for table in tables:
                if not self._safe_table_name(table):
                    continue
                count = self._count_rows(conn, table)
                columns = self._columns(conn, table)
                lines.append(f"- {table}: {count} dong; cot: {', '.join(columns[:10])}")
                sample = self._sample_rows(conn, table, columns[:5])
                for row in sample:
                    lines.append(f"  mau: {row}")
            conn.close()
        except Exception as exc:
            lines.append(f"Khong doc duoc ngu canh bang: {exc}")
        return "\n".join(lines)

    def _safe_table_name(self, table: str) -> bool:
        return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table))

    def _count_rows(self, conn: sqlite3.Connection, table: str) -> int:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cursor.fetchone()[0])

    def _columns(self, conn: sqlite3.Connection, table: str) -> List[str]:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cursor.fetchall()]

    def _sample_rows(self, conn: sqlite3.Connection, table: str, columns: List[str]) -> List[Dict]:
        if not columns:
            return []
        safe_cols = [col for col in columns if self._safe_table_name(col)]
        if not safe_cols:
            return []
        cursor = conn.cursor()
        cursor.execute(f"SELECT {', '.join(safe_cols)} FROM {table} LIMIT 3")
        return [dict(row) for row in cursor.fetchall()]
