"""FastAPI 应用入口 —— 创建 app、CORS、路由挂载、自动建表与 seed。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时建表并 seed 预设数据，关闭时清理资源。"""
    # 启动：建表
    await init_db()

    # 启动：seed 预设模板
    from seed import seed_templates
    from database import async_session_factory

    async with async_session_factory() as session:
        await seed_templates(session)
        await session.commit()

    yield


app = FastAPI(
    title="墨境 · 小说写作助手",
    description="AI 驱动的故事策划、卡片梳理与大纲生成后端",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS —— 开发阶段允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 路由挂载 ───────────────────────────────────────────

from routers.auth import router as auth_router
from routers.projects import router as projects_router
from routers.cards import router as cards_router
from routers.organize import router as organize_router
from routers.outlines import router as outlines_router

app.include_router(auth_router, prefix="/auth", tags=["认证"])
app.include_router(projects_router, prefix="/projects", tags=["项目"])
app.include_router(cards_router, prefix="/projects", tags=["卡片"])
app.include_router(organize_router, prefix="/organize", tags=["梳理"])
app.include_router(outlines_router, prefix="/outlines", tags=["大纲"])


@app.get("/")
async def root():
    """健康检查。"""
    return {"message": "墨境 · 小说写作助手 API", "status": "running"}


# ─── 直接启动 ───────────────────────────────────────────

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", "9003"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
