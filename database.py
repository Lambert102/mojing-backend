"""数据库引擎与会话工厂。使用 SQLAlchemy 2.0 async 引擎 + aiosqlite。"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# 异步引擎 —— SQLite WAL 模式通过 aiosqlite 连接参数启用
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

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
