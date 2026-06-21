"""卡片路由 —— GET /projects/{id}/cards, POST /projects/{id}/cards, DELETE /projects/{id}/cards/{card_id}。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Card, User
from schemas import CardCreate, CardResponse, CardUpdate
from auth import get_current_user
from routers.projects import get_owned_project

router = APIRouter()


@router.get("/{project_id}/cards", response_model=list[CardResponse])
async def list_cards(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Card]:
    """获取指定项目的所有卡片，按 order_index 排序。"""
    # 验证项目所有权
    await get_owned_project(project_id, current_user, db)

    result = await db.execute(
        select(Card)
        .where(Card.project_id == project_id)
        .order_by(Card.order_index, Card.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/{project_id}/cards",
    response_model=CardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_card(
    project_id: int,
    body: CardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Card:
    """在指定项目中创建一张新卡片。"""
    # 验证项目所有权
    await get_owned_project(project_id, current_user, db)

    card = Card(
        project_id=project_id,
        title=body.title,
        content=body.content,
        type=body.type,
        order_index=body.order_index,
        color=body.color,
    )
    db.add(card)
    await db.flush()
    await db.refresh(card)
    return card


@router.get("/{project_id}/cards/{card_id}", response_model=CardResponse)
async def get_card(
    project_id: int,
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Card:
    """获取单张卡片详情。"""
    await get_owned_project(project_id, current_user, db)
    card = await _get_card_in_project(project_id, card_id, db)
    return card


@router.patch("/{project_id}/cards/{card_id}", response_model=CardResponse)
async def update_card(
    project_id: int,
    card_id: int,
    body: CardUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Card:
    """更新卡片内容。"""
    await get_owned_project(project_id, current_user, db)
    card = await _get_card_in_project(project_id, card_id, db)

    if body.title is not None:
        card.title = body.title
    if body.content is not None:
        card.content = body.content
    if body.type is not None:
        card.type = body.type
    if body.order_index is not None:
        card.order_index = body.order_index
    if body.color is not None:
        card.color = body.color

    await db.flush()
    await db.refresh(card)
    return card


@router.delete(
    "/{project_id}/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_card(
    project_id: int,
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除指定卡片。"""
    await get_owned_project(project_id, current_user, db)
    card = await _get_card_in_project(project_id, card_id, db)
    await db.delete(card)
    await db.flush()


# ─── 工具函数 ───────────────────────────────────────────

async def _get_card_in_project(
    project_id: int, card_id: int, db: AsyncSession
) -> Card:
    """获取属于指定项目的卡片。"""
    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.project_id == project_id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="卡片不存在",
        )
    return card
