"""项目路由 —— GET /projects, POST /projects。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Project, User
from schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from auth import get_current_user

router = APIRouter()


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    """获取当前用户的所有项目列表。"""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """创建新项目。"""
    project = Project(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """获取单个项目详情。"""
    project = await get_owned_project(project_id, current_user, db)
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """更新项目名称或描述。"""
    project = await get_owned_project(project_id, current_user, db)

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description

    await db.flush()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除项目（级联删除其下所有卡片、梳理结果、大纲结果）。"""
    project = await get_owned_project(project_id, current_user, db)
    await db.delete(project)
    await db.flush()


# ─── 工具函数 ───────────────────────────────────────────

async def get_owned_project(
    project_id: int, user: User, db: AsyncSession
) -> Project:
    """获取项目并验证所有权。"""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )
    return project
