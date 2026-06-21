"""梳理路由 —— POST /organize/{project_id}, GET /organize/{project_id}。

调用 DeepSeek 分析项目下所有卡片，生成叙事结构、人物、伏笔的结构化结果。
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Card, OrganizeResult, User
from schemas import OrganizeResponse
from auth import get_current_user
from routers.projects import get_owned_project
from services.deepseek_service import deepseek_service

router = APIRouter()


@router.get("/{project_id}", response_model=OrganizeResponse)
async def get_organize_result(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizeResult:
    """获取项目的最新梳理结果。"""
    await get_owned_project(project_id, current_user, db)

    result = await db.execute(
        select(OrganizeResult)
        .where(OrganizeResult.project_id == project_id)
        .order_by(OrganizeResult.created_at.desc())
        .limit(1)
    )
    organize_result = result.scalar_one_or_none()
    if organize_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该项目尚无梳理结果，请先执行梳理",
        )
    return organize_result


@router.post(
    "/{project_id}", response_model=OrganizeResponse, status_code=status.HTTP_201_CREATED
)
async def run_organize(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizeResult:
    """执行梳理：收集项目下所有卡片，调用 DeepSeek 分析并存储结果。"""
    # 验证项目所有权
    await get_owned_project(project_id, current_user, db)

    # 获取项目下所有卡片
    cards_result = await db.execute(
        select(Card)
        .where(Card.project_id == project_id)
        .order_by(Card.order_index)
    )
    cards = list(cards_result.scalars().all())

    if not cards:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目中没有卡片，请先添加卡片后再执行梳理",
        )

    # 构建卡片数据
    cards_data: list[dict] = [
        {
            "id": card.id,
            "title": card.title,
            "content": card.content,
            "type": card.type,
        }
        for card in cards
    ]

    # 调用 DeepSeek
    try:
        organize_json = await deepseek_service.organize(cards_data)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DeepSeek API 调用失败: {exc}",
        )

    # 存储结果
    result_str = json.dumps(organize_json, ensure_ascii=False)
    organize_result = OrganizeResult(
        project_id=project_id,
        result_json=result_str,
    )
    db.add(organize_result)
    await db.flush()
    await db.refresh(organize_result)
    return organize_result
