# -*- coding: utf-8 -*-
"""
配置管理模块
从 .env 文件读取所有环境变量，提供类型安全的配置对象
所有敏感信息（API Key、密钥等）均通过环境变量注入，不硬编码
"""
import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)


class Settings:
    """
    应用配置类
    所有配置项从环境变量读取，未配置时使用默认值
    """

    # ===== 域名 =====
    DOMAIN: str = os.getenv("DOMAIN", "pb.d9g.com.cn")

    # ===== 智谱 AI =====
    ZHIPU_API_URL: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    ZHIPU_API_KEY: str = os.getenv("ZHIPU_API_KEY", "")

    # ===== 微信小程序 =====
    MINI_APP_ID: str = os.getenv("MINI_APP_ID", "")
    MINI_APP_SECRET: str = os.getenv("MINI_APP_SECRET", "")

    # ===== Redis =====
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ===== 管理密钥 =====
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "")

    # ===== 服务配置 =====
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ===== AI 模型配置 =====
    # 切换模型只需改 .env 中这两项，无需改任何代码
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "zhipu")
    AI_MODEL: str = os.getenv("AI_MODEL", "glm-4-flash")

    # ===== 业务限制 =====
    MAX_INPUT_LENGTH: int = 3000
    MIN_INPUT_LENGTH: int = 50
    RATE_LIMIT_PER_HOUR: int = 10
    VERIFY_VALID_DAYS: int = 30
    VERIFY_CODE_EXPIRE_SECONDS: int = 300
    VERIFY_KEYWORD: str = "排版"

    # ===== 路径 =====
    PROMPTS_DIR: Path = BASE_DIR / "prompts"
    STATIC_DIR: Path = BASE_DIR / "static"
    DB_PATH: Path = BASE_DIR / "data.db"

    @classmethod
    def get_account_pool(cls) -> list[dict]:
        """
        从环境变量动态构建公众号池
        支持 A-Z 共 26 个公众号槽位，按需配置
        """
        pool = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            prefix = f"ACCOUNT_{letter}"
            account_id = os.getenv(f"{prefix}_ID")
            if not account_id:
                continue
            pool.append({
                "id": account_id,
                "name": os.getenv(f"{prefix}_NAME", ""),
                "description": os.getenv(f"{prefix}_DESC", ""),
                "app_id": os.getenv(f"{prefix}_APP_ID", ""),
                "app_secret": os.getenv(f"{prefix}_APP_SECRET", ""),
                "token": os.getenv(f"{prefix}_TOKEN", ""),
                "encoding_aes_key": os.getenv(f"{prefix}_AES_KEY", ""),
                "avatar": os.getenv(f"{prefix}_AVATAR", ""),
                "qrcode": os.getenv(f"{prefix}_QRCODE", ""),
            })
        return pool

    @classmethod
    def validate(cls) -> list[str]:
        """
        校验必要配置是否已填写
        返回缺失的配置项列表
        """
        warnings = []
        if not cls.ZHIPU_API_KEY:
            warnings.append("ZHIPU_API_KEY 未配置，AI 排版功能不可用")
        if not cls.MINI_APP_ID:
            warnings.append("MINI_APP_ID 未配置，微信登录不可用")
        if not cls.ADMIN_SECRET_KEY:
            warnings.append("ADMIN_SECRET_KEY 未配置，管理接口不安全")
        if not cls.get_account_pool():
            warnings.append("未配置任何公众号，关注验证不可用")
        return warnings


settings = Settings()
