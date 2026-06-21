"""Pydantic Schema 定义 —— 请求/响应模型的序列化与验证。"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ─── Auth ──────────────────────────────────────────────

class UserRegister(BaseModel):
    """注册请求体。"""
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    """登录请求体。"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """登录成功的 token 响应。"""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """用户信息响应。"""
    id: int
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Project ───────────────────────────────────────────

class ProjectCreate(BaseModel):
    """创建项目请求体。"""
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class ProjectUpdate(BaseModel):
    """更新项目请求体。"""
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    """项目响应体。"""
    id: int
    user_id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Card ──────────────────────────────────────────────

class CardCreate(BaseModel):
    """创建卡片请求体。"""
    title: str = Field(min_length=1, max_length=255)
    content: str = ""
    type: str = Field(default="note", pattern=r"^(character|plot|setting|note)$")
    order_index: int = 0
    color: str = "#ffffff"


class CardUpdate(BaseModel):
    """更新卡片请求体。"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    type: Optional[str] = Field(None, pattern=r"^(character|plot|setting|note)$")
    order_index: Optional[int] = None
    color: Optional[str] = None


class CardResponse(BaseModel):
    """卡片响应体。"""
    id: int
    project_id: int
    title: str
    content: str
    type: str
    order_index: int
    color: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Organize ──────────────────────────────────────────

class OrganizeResponse(BaseModel):
    """梳理结果响应体。"""
    id: int
    project_id: int
    result_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Outline Template ──────────────────────────────────

class OutlineTemplateCreate(BaseModel):
    """创建大纲模板请求体。"""
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    structure_json: str  # JSON 字符串


class OutlineTemplateResponse(BaseModel):
    """大纲模板响应体。"""
    id: int
    name: str
    description: str
    structure_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Outline Result ────────────────────────────────────

class OutlineGenerateRequest(BaseModel):
    """大纲生成请求体。"""
    template_id: int


class OutlineExportRequest(BaseModel):
    """大纲导出请求体（支持格式选择）。"""
    format: str = Field(default="json", pattern=r"^(json|markdown|txt)$")


class OutlineResultResponse(BaseModel):
    """大纲生成结果响应体。"""
    id: int
    project_id: int
    template_id: Optional[int]
    result_json: str
    created_at: datetime

    model_config = {"from_attributes": True}
