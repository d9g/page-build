# -*- coding: utf-8 -*-
"""
数据库模块
使用 SQLite + aiosqlite 提供异步数据库操作
首次启动自动建表，无需手动初始化
"""
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

# 建表 SQL
INIT_SQL = """
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    openid TEXT UNIQUE NOT NULL,
    session_key TEXT,
    verified INTEGER DEFAULT 0,
    verified_account TEXT,
    verified_at TIMESTAMP,
    verify_expires_at TIMESTAMP,
    layout_count INTEGER DEFAULT 0,
    last_layout_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 排版记录表
CREATE TABLE IF NOT EXISTS layout_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    input_text TEXT NOT NULL,
    input_length INTEGER,
    output_html TEXT,
    output_sections TEXT,
    theme TEXT DEFAULT 'default',
    ai_model TEXT,
    ai_tokens_used INTEGER,
    process_time_ms INTEGER,
    prompt_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 验证日志表
CREATE TABLE IF NOT EXISTS verify_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    code TEXT,
    account_id TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 推广账号切换日志表
CREATE TABLE IF NOT EXISTS account_switch_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_account TEXT NOT NULL,
    to_account TEXT NOT NULL,
    operator TEXT DEFAULT 'admin',
    reason TEXT,
    switched_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_users_openid ON users(openid);
CREATE INDEX IF NOT EXISTS idx_layout_records_user ON layout_records(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_verify_logs_user ON verify_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_verify_logs_account ON verify_logs(account_id, created_at DESC);
"""


class Database:
    """
    异步数据库操作封装
    使用连接池模式，避免频繁创建/关闭连接
    """

    def __init__(self):
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """建立数据库连接并初始化表结构"""
        self._db = await aiosqlite.connect(str(settings.DB_PATH))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(INIT_SQL)
        await self._db.commit()
        logger.info(f"数据库已连接: {settings.DB_PATH}")

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            logger.info("数据库连接已关闭")

    # ===== 用户操作 =====

    async def get_user_by_openid(self, openid: str) -> Optional[dict]:
        """根据 openid 查询用户"""
        async with self._db.execute(
            "SELECT * FROM users WHERE openid = ?", (openid,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_or_update_user(
        self, openid: str, session_key: str
    ) -> dict:
        """
        创建或更新用户
        首次登录创建用户记录，后续登录更新 session_key
        """
        user = await self.get_user_by_openid(openid)
        if user:
            await self._db.execute(
                "UPDATE users SET session_key = ?, updated_at = ? WHERE openid = ?",
                (session_key, datetime.now().isoformat(), openid),
            )
            await self._db.commit()
            return await self.get_user_by_openid(openid)

        await self._db.execute(
            "INSERT INTO users (openid, session_key) VALUES (?, ?)",
            (openid, session_key),
        )
        await self._db.commit()
        return await self.get_user_by_openid(openid)

    async def check_user_verified(self, openid: str) -> bool:
        """检查用户是否已验证关注（且未过期）"""
        user = await self.get_user_by_openid(openid)
        if not user or not user["verified"]:
            return False
        if user["verify_expires_at"]:
            expires = datetime.fromisoformat(user["verify_expires_at"])
            if datetime.now() > expires:
                return False
        return True

    async def save_verification(
        self, mini_openid: str, account_id: str, expires_at: datetime
    ) -> None:
        """保存验证通过状态"""
        await self._db.execute(
            """UPDATE users SET
                verified = 1,
                verified_account = ?,
                verified_at = ?,
                verify_expires_at = ?,
                updated_at = ?
            WHERE openid = ?""",
            (
                account_id,
                datetime.now().isoformat(),
                expires_at.isoformat(),
                datetime.now().isoformat(),
                mini_openid,
            ),
        )
        await self._db.commit()

    # ===== 排版记录 =====

    async def save_layout_record(
        self,
        user_id: int,
        input_text: str,
        output_html: str,
        theme: str,
        ai_model: str,
        ai_tokens_used: int,
        process_time_ms: int,
        prompt_version: str,
    ) -> int:
        """保存排版记录，返回记录 ID"""
        cursor = await self._db.execute(
            """INSERT INTO layout_records
                (user_id, input_text, input_length, output_html, theme,
                 ai_model, ai_tokens_used, process_time_ms, prompt_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                input_text[:500],  # 只存前 500 字做摘要
                len(input_text),
                output_html,
                theme,
                ai_model,
                ai_tokens_used,
                process_time_ms,
                prompt_version,
            ),
        )
        await self._db.execute(
            """UPDATE users SET
                layout_count = layout_count + 1,
                last_layout_at = ?,
                updated_at = ?
            WHERE id = ?""",
            (datetime.now().isoformat(), datetime.now().isoformat(), user_id),
        )
        await self._db.commit()
        return cursor.lastrowid

    # ===== 验证日志 =====

    async def log_verification(
        self, user_id: Optional[int], code: str, account_id: str, status: str
    ) -> None:
        """记录验证操作日志"""
        await self._db.execute(
            "INSERT INTO verify_logs (user_id, code, account_id, status) VALUES (?, ?, ?, ?)",
            (user_id, code, account_id, status),
        )
        await self._db.commit()

    async def count_verifications(
        self, account_id: str, since: Optional[datetime] = None
    ) -> int:
        """统计某公众号的验证通过次数"""
        if since:
            async with self._db.execute(
                "SELECT COUNT(*) FROM verify_logs WHERE account_id = ? AND status = 'success' AND created_at >= ?",
                (account_id, since.isoformat()),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]
        else:
            async with self._db.execute(
                "SELECT COUNT(*) FROM verify_logs WHERE account_id = ? AND status = 'success'",
                (account_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]

    # ===== 推广账号切换日志 =====

    async def log_account_switch(
        self,
        from_account: str,
        to_account: str,
        operator: str,
        switched_at: datetime,
        reason: Optional[str] = None,
    ) -> None:
        """记录推广账号切换操作"""
        await self._db.execute(
            "INSERT INTO account_switch_logs (from_account, to_account, operator, reason, switched_at) VALUES (?, ?, ?, ?, ?)",
            (from_account, to_account, operator, reason, switched_at.isoformat()),
        )
        await self._db.commit()


# 全局数据库实例
db = Database()
