"""数据库引擎与会话工厂。支持 SQLite (本地开发) / PostgreSQL (生产)。"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# 异步引擎 —— 根据 DATABASE_URL 自动选择 SQLite 或 PostgreSQL
_db_url = settings.DATABASE_URL
_engine_kwargs = {"echo": False}
if "sqlite" in _db_url:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(_db_url, **_engine_kwargs)

# 会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """声明式基类，所有 ORM 模型继承自此。"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖：为每个请求生成一个数据库会话，结束后自动关闭。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """创建所有表（如不存在）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
