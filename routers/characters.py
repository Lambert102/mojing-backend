"""人物卡路由 —— CRUD：GET/POST/PATCH/DELETE /projects/{project_id}/characters。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CharacterCard, User
from schemas import CharacterCardCreate, CharacterCardResponse, CharacterCardUpdate
from auth import get_current_user
from routers.projects import get_owned_project

router = APIRouter()


@router.get(
    "/{project_id}/characters",
    response_model=list[CharacterCardResponse],
)
async def list_characters(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CharacterCard]:
    """获取指定项目下的所有人物设定卡，按更新时间倒序排列。"""
    await get_owned_project(project_id, current_user, db)

    result = await db.execute(
        select(CharacterCard)
        .where(CharacterCard.project_id == project_id)
        .order_by(CharacterCard.updated_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{project_id}/characters",
    response_model=CharacterCardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_character(
    project_id: int,
    body: CharacterCardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CharacterCard:
    """在指定项目中创建一张新的人物设定卡。"""
    await get_owned_project(project_id, current_user, db)

    char = CharacterCard(
        project_id=project_id,
        name=body.name,
        surface_persona=body.surface_persona,
        actual_persona=body.actual_persona,
        appearance=body.appearance,
        personality=body.personality,
        growth_arc=body.growth_arc,
        relationships=body.relationships,
        functional_role=body.functional_role,
    )
    db.add(char)
    await db.flush()
    await db.refresh(char)
    return char


@router.get(
    "/{project_id}/characters/{char_id}",
    response_model=CharacterCardResponse,
)
async def get_character(
    project_id: int,
    char_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CharacterCard:
    """获取单张人物设定卡详情。"""
    await get_owned_project(project_id, current_user, db)
    char = await _get_character_in_project(project_id, char_id, db)
    return char


@router.patch(
    "/{project_id}/characters/{char_id}",
    response_model=CharacterCardResponse,
)
async def update_character(
    project_id: int,
    char_id: int,
    body: CharacterCardUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CharacterCard:
    """更新人物设定卡内容。"""
    await get_owned_project(project_id, current_user, db)
    char = await _get_character_in_project(project_id, char_id, db)

    if body.name is not None:
        char.name = body.name
    if body.surface_persona is not None:
        char.surface_persona = body.surface_persona
    if body.actual_persona is not None:
        char.actual_persona = body.actual_persona
    if body.appearance is not None:
        char.appearance = body.appearance
    if body.personality is not None:
        char.personality = body.personality
    if body.growth_arc is not None:
        char.growth_arc = body.growth_arc
    if body.relationships is not None:
        char.relationships = body.relationships
    if body.functional_role is not None:
        char.functional_role = body.functional_role

    await db.flush()
    await db.refresh(char)
    return char


@router.delete(
    "/{project_id}/characters/{char_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_character(
    project_id: int,
    char_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除指定人物设定卡（级联删除其下所有会话和消息）。"""
    await get_owned_project(project_id, current_user, db)
    char = await _get_character_in_project(project_id, char_id, db)
    await db.delete(char)
    await db.flush()


# ─── 工具函数 ───────────────────────────────────────────

async def _get_character_in_project(
    project_id: int, char_id: int, db: AsyncSession
) -> CharacterCard:
    """获取属于指定项目的人物设定卡。"""
    result = await db.execute(
        select(CharacterCard).where(
            CharacterCard.id == char_id,
            CharacterCard.project_id == project_id,
        )
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="人物设定卡不存在",
        )
    return char
