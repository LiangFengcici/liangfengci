"""数据访问层：SQLite 连接、建库、审计与单据号生成。

设计对应 4.10「数据层」：原型期用 SQLite 单库，生产替换为 MySQL 主从 +
只读报表库，接口契约（SQL 语义）保持不变。
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from flask import g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "dental.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# 全系统统一时区：东八区
TZ = timezone(timedelta(hours=8))


def now() -> str:
    """ISO 8601 带时区（附录A 通用数据约定）。"""
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        g.db = conn
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql: str, args=(), one: bool = False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql: str, args=()):
    return get_db().execute(sql, args)


def init_db(force: bool = False):
    """一次建库、不再临场改表（5.1 原则二）。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def gen_no(prefix: str) -> str:
    """业务单号：前缀 + 时间 + 4 位随机，满足唯一约束。"""
    return f"{prefix}{datetime.now(TZ):%Y%m%d%H%M%S}{uuid.uuid4().hex[:4].upper()}"


def audit(action: str, target: str = "", before=None, after=None,
          actor: str | None = None, role: str | None = None, ip: str = ""):
    """全部敏感操作写审计日志（4.12）。"""
    from flask import has_request_context, session, request
    if actor is None:
        if has_request_context():
            actor = session.get("display_name") or session.get("patient_name") or "匿名"
            role = role or session.get("role") or ""
            ip = ip or (request.headers.get("X-Forwarded-For", request.remote_addr or ""))
        else:
            actor = actor or "系统(定时任务)"
    execute(
        """INSERT INTO audit_log(account_id, actor, role, action, target,
                                 before_json, after_json, ip, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (None, actor, role, action, target,
         _json(before), _json(after), ip, now()),
    )


def _json(v):
    import json
    if v is None:
        return None
    return json.dumps(v, ensure_ascii=False, default=str)


def money(cents) -> str:
    if cents is None:
        return "¥0.00"
    return f"¥{cents / 100:,.2f}"
