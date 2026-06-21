"""应用配置模块 —— 从环境变量 / .env 文件读取配置。"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """全局配置单例。"""

    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # Database (从环境变量读取，自动适配 SQLite/PostgreSQL)
    _raw_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./novel_app.db")
    # Neon 给的 URL 是 postgresql://, SQLAlchemy async 需要 postgresql+asyncpg://
    if _raw_url.startswith("postgresql://") and not _raw_url.startswith("postgresql+asyncpg"):
        _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg 用 ?ssl=require 代替 ?sslmode=require
        _raw_url = _raw_url.replace("?sslmode=require", "?ssl=require")
    DATABASE_URL: str = _raw_url


settings = Settings()

