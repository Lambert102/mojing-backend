"""对话路由 —— 会话管理 + AI 角色扮演聊天。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import CharacterCard, ChatMessage, ChatSession, User
from schemas import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
)
from auth import get_current_user
from routers.projects import get_owned_project
from routers.characters import _get_character_in_project
from services.deepseek_service import deepseek_service

router = APIRouter()


# ─── 会话 CRUD ──────────────────────────────────────────

@router.get(
    "/projects/{project_id}/characters/{char_id}/sessions",
    response_model=list[ChatSessionResponse],
)
async def list_sessions(
    project_id: int,
    char_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatSession]:
    """获取某个角色下的所有对话会话，按更新时间倒序排列。"""
    await get_owned_project(project_id, current_user, db)
    await _get_character_in_project(project_id, char_id, db)

    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.character_card_id == char_id,
            ChatSession.project_id == project_id,
        )
        .order_by(ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/projects/{project_id}/characters/{char_id}/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    project_id: int,
    char_id: int,
    body: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSession:
    """为指定角色创建一个新的对话会话。"""
    await get_owned_project(project_id, current_user, db)
    await _get_character_in_project(project_id, char_id, db)

    session = ChatSession(
        character_card_id=char_id,
        project_id=project_id,
        title=body.title,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
)
async def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessage]:
    """获取指定会话的所有消息，按时间正序排列。"""
    session = await _get_owned_session(session_id, current_user, db)

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return list(result.scalars().all())


@router.patch(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
)
async def update_session(
    session_id: int,
    body: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSession:
    """更新会话标题。"""
    session = await _get_owned_session(session_id, current_user, db)

    if body.title is not None:
        session.title = body.title

    await db.flush()
    await db.refresh(session)
    return session


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除指定对话会话（级联删除其下所有消息）。"""
    session = await _get_owned_session(session_id, current_user, db)
    await db.delete(session)
    await db.flush()


# ─── 核心：角色扮演对话 ─────────────────────────────────

@router.post(
    "/sessions/{session_id}/chat",
    response_model=ChatResponse,
)
async def send_message(
    session_id: int,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """向角色发送消息并获取 AI 回复。

    工作流程：
    1. 验证会话所有权
    2. 获取角色设定卡
    3. 获取历史消息
    4. 调用 DeepSeek 角色扮演
    5. 保存用户消息和 AI 回复
    6. 返回 AI 回复
    """
    session = await _get_owned_session(session_id, current_user, db)

    # 获取角色设定卡
    char_result = await db.execute(
        select(CharacterCard).where(CharacterCard.id == session.character_card_id)
    )
    character_card = char_result.scalar_one_or_none()
    if character_card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色设定卡不存在",
        )

    # 获取历史消息
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    history_messages = list(history_result.scalars().all())

    # 保存用户消息
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=body.content,
    )
    db.add(user_msg)

    # 构建历史消息列表（用于 API 调用）
    # 注意：先保存用户消息，但不作为历史传给 AI（AI 在 messages 数组末尾接收用户消息）
    history_for_api: list[dict[str, str]] = []
    for msg in history_messages:
        history_for_api.append({"role": msg.role, "content": msg.content})

    # 调用 AI 角色扮演
    reply_content = await deepseek_service.roleplay_chat(
        character_card=character_card,
        messages=history_for_api,
        user_message=body.content,
    )

    # 保存 AI 回复
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=reply_content,
    )
    db.add(assistant_msg)

    await db.flush()

    return {"role": "assistant", "content": reply_content}


@router.post(
    "/sessions/{session_id}/greeting",
    response_model=ChatResponse,
)
async def get_greeting(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取 AI 开场白：首次进入对话时调用，AI 主动打招呼。

    工作流程：
    1. 验证会话所有权
    2. 获取角色设定卡
    3. 调用 roleplay_chat（空消息 + 空历史），让 AI 主动生成开场白
    4. 保存 AI 开场白
    5. 返回开场白内容
    """
    session = await _get_owned_session(session_id, current_user, db)

    # 防重复调用：已存在消息则返回 409
    existing_msg_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).limit(1)
    )
    if existing_msg_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="开场白已生成，请使用 /chat 继续对话",
        )

    # 获取角色设定卡
    char_result = await db.execute(
        select(CharacterCard).where(CharacterCard.id == session.character_card_id)
    )
    character_card = char_result.scalar_one_or_none()
    if character_card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="角色设定卡不存在",
        )

    # 调用 AI 生成开场白
    greeting_content = await deepseek_service.roleplay_chat(
        character_card=character_card,
        messages=[],
        user_message="请以角色的身份主动向作者打招呼",
    )

    # 保存 AI 开场白
    greeting_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=greeting_content,
    )
    db.add(greeting_msg)
    await db.flush()

    return {"role": "assistant", "content": greeting_content}


# ─── 工具函数 ───────────────────────────────────────────

async def _get_owned_session(
    session_id: int, user: User, db: AsyncSession
) -> ChatSession:
    """获取会话并验证所有权（通过 project -> user 链路）。"""
    # 先查会话是否存在
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话会话不存在",
        )

    # 验证项目所有权
    await get_owned_project(session.project_id, user, db)

    return session
