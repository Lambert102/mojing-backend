"""大纲路由 —— 模板管理与大纲生成。

端点：
- GET  /outlines/templates          — 获取所有模板
- POST /outlines/templates          — 创建自定义模板
- POST /outlines/{project_id}/generate — 为项目生成大纲
- POST /outlines/{project_id}/export   — 导出大纲为 Markdown/TXT
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import (
    Card,
    OrganizeResult,
    OutlineResult,
    OutlineTemplate,
    User,
)
from schemas import (
    OutlineExportRequest,
    OutlineGenerateRequest,
    OutlineResultResponse,
    OutlineTemplateCreate,
    OutlineTemplateResponse,
)
from auth import get_current_user
from routers.projects import get_owned_project
from services.deepseek_service import deepseek_service

router = APIRouter()


# ─── 模板管理 ───────────────────────────────────────────

@router.get("/templates", response_model=list[OutlineTemplateResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
) -> list[OutlineTemplate]:
    """获取所有大纲模板（无需认证）。"""
    result = await db.execute(
        select(OutlineTemplate).order_by(OutlineTemplate.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/templates",
    response_model=OutlineTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    body: OutlineTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutlineTemplate:
    """创建自定义大纲模板（需认证）。"""
    # 检查名称唯一性
    existing = await db.execute(
        select(OutlineTemplate).where(OutlineTemplate.name == body.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模板名称已存在",
        )

    # 验证 structure_json 为合法 JSON
    try:
        json.loads(body.structure_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="structure_json 不是合法的 JSON 字符串",
        )

    template = OutlineTemplate(
        name=body.name,
        description=body.description,
        structure_json=body.structure_json,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@router.delete(
    "/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除自定义模板（需认证）。"""
    result = await db.execute(
        select(OutlineTemplate).where(OutlineTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在",
        )
    await db.delete(template)
    await db.flush()


# ─── 大纲生成 ───────────────────────────────────────────

@router.post(
    "/{project_id}/generate",
    response_model=OutlineResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_outline(
    project_id: int,
    body: OutlineGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutlineResult:
    """为指定项目按模板生成大纲。

    需要项目已有梳理结果。
    """
    # 验证项目所有权
    await get_owned_project(project_id, current_user, db)

    # 获取模板
    template_result = await db.execute(
        select(OutlineTemplate).where(OutlineTemplate.id == body.template_id)
    )
    template = template_result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定的模板不存在",
        )

    # 获取最新梳理结果
    organize_result = await db.execute(
        select(OrganizeResult)
        .where(OrganizeResult.project_id == project_id)
        .order_by(OrganizeResult.created_at.desc())
        .limit(1)
    )
    org = organize_result.scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该项目尚未执行梳理，请先调用 /organize/{project_id} 进行梳理",
        )

    # 获取卡片数据
    cards_result = await db.execute(
        select(Card)
        .where(Card.project_id == project_id)
        .order_by(Card.order_index)
    )
    cards = list(cards_result.scalars().all())

    cards_data: list[dict] = [
        {"id": card.id, "title": card.title, "content": card.content, "type": card.type}
        for card in cards
    ]

    # 解析 JSON
    organize_json: dict = json.loads(org.result_json)
    template_json: dict = json.loads(template.structure_json)

    # 调用 DeepSeek 生成大纲
    try:
        outline_json = await deepseek_service.generate_outline(
            organize_result=organize_json,
            template_structure=template_json,
            cards_data=cards_data,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DeepSeek API 调用失败: {exc}",
        )

    # 存储结果
    result_str = json.dumps(outline_json, ensure_ascii=False)
    outline_result = OutlineResult(
        project_id=project_id,
        template_id=template.id,
        result_json=result_str,
    )
    db.add(outline_result)
    await db.flush()
    await db.refresh(outline_result)
    return outline_result


@router.get(
    "/{project_id}/results", response_model=list[OutlineResultResponse]
)
async def list_outline_results(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OutlineResult]:
    """获取项目下所有大纲生成结果。"""
    await get_owned_project(project_id, current_user, db)

    result = await db.execute(
        select(OutlineResult)
        .where(OutlineResult.project_id == project_id)
        .order_by(OutlineResult.created_at.desc())
    )
    return list(result.scalars().all())


# ─── 大纲导出 ───────────────────────────────────────────

@router.post("/{project_id}/export")
async def export_outline(
    project_id: int,
    body: OutlineExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """导出项目最新大纲为指定格式。

    返回 JSON 对象，包含 format 和 content 字段。
    """
    await get_owned_project(project_id, current_user, db)

    # 获取最新大纲结果
    result = await db.execute(
        select(OutlineResult)
        .where(OutlineResult.project_id == project_id)
        .order_by(OutlineResult.created_at.desc())
        .limit(1)
    )
    outline_result = result.scalar_one_or_none()
    if outline_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该项目尚无大纲生成结果",
        )

    outline_json: dict = json.loads(outline_result.result_json)

    if body.format == "json":
        content = json.dumps(outline_json, ensure_ascii=False, indent=2)
    elif body.format == "markdown":
        content = _outline_to_markdown(outline_json)
    elif body.format == "txt":
        content = _outline_to_text(outline_json)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的导出格式: {body.format}",
        )

    return {"format": body.format, "content": content}


# ─── 格式转换工具 ────────────────────────────────────────

def _outline_to_markdown(outline: dict) -> str:
    """将大纲 JSON 转换为 Markdown。"""
    lines: list[str] = []

    title = outline.get("summary", "小说大纲")
    lines.append(f"# {title}")
    lines.append("")

    chapters = outline.get("chapters", [])
    for ch in chapters:
        num = ch.get("number", "")
        ch_title = ch.get("title", "")
        lines.append(f"## 第{num}章 {ch_title}")
        lines.append("")

        conflict = ch.get("core_conflict", "")
        if conflict:
            lines.append(f"**核心冲突**: {conflict}")
            lines.append("")

        events = ch.get("key_events", [])
        if events:
            lines.append("### 关键事件")
            for ev in events:
                lines.append(f"- {ev}")
            lines.append("")

        chars = ch.get("characters_involved", [])
        if chars:
            lines.append(f"**涉及人物**: {', '.join(chars)}")
            lines.append("")

        planted = ch.get("foreshadowing_planted", [])
        if planted:
            lines.append("**埋下伏笔**:")
            for f in planted:
                lines.append(f"- {f}")
            lines.append("")

        resolved = ch.get("foreshadowing_resolved", [])
        if resolved:
            lines.append("**伏笔回收**:")
            for f in resolved:
                lines.append(f"- {f}")
            lines.append("")

    return "\n".join(lines)


def _outline_to_text(outline: dict) -> str:
    """将大纲 JSON 转换为纯文本。"""
    lines: list[str] = []

    title = outline.get("summary", "小说大纲")
    lines.append(f"《{title}》")
    lines.append("=" * 40)

    chapters = outline.get("chapters", [])
    for ch in chapters:
        num = ch.get("number", "")
        ch_title = ch.get("title", "")
        lines.append(f"\n第{num}章 {ch_title}")
        lines.append("-" * 30)

        conflict = ch.get("core_conflict", "")
        if conflict:
            lines.append(f"核心冲突: {conflict}")

        events = ch.get("key_events", [])
        if events:
            lines.append("关键事件:")
            for i, ev in enumerate(events, 1):
                lines.append(f"  {i}. {ev}")

        chars = ch.get("characters_involved", [])
        if chars:
            lines.append(f"涉及人物: {', '.join(chars)}")

    return "\n".join(lines)
