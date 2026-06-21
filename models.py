"""ORM 模型定义 —— 6 张表：users → projects → cards / organize_results / outline_results / outline_templates。"""

import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, server_default=func.now()
    )

    # 关系
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class Project(Base):
    """项目表 —— 一个项目对应一部小说的策划。"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        server_default=func.now(),
        onupdate=datetime.datetime.utcnow,
    )

    # 关系
    user = relationship("User", back_populates="projects")
    cards = relationship("Card", back_populates="project", cascade="all, delete-orphan")
    organize_results = relationship(
        "OrganizeResult", back_populates="project", cascade="all, delete-orphan"
    )
    outline_results = relationship(
        "OutlineResult", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


class Card(Base):
    """卡片表 —— 故事要素卡片（人物、情节、设定、笔记）。"""

    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(255), nullable=False)
    content = Column(Text, default="")
    type = Column(
        String(32), nullable=False, default="note"
    )  # character / plot / setting / note
    order_index = Column(Integer, default=0)
    color = Column(String(16), default="#ffffff")
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        server_default=func.now(),
        onupdate=datetime.datetime.utcnow,
    )

    # 关系
    project = relationship("Project", back_populates="cards")

    def __repr__(self) -> str:
        return f"<Card id={self.id} title={self.title!r} type={self.type!r}>"


class OrganizeResult(Base):
    """梳理结果表 —— DeepSeek 分析卡片后产出的结构化 JSON。"""

    __tablename__ = "organize_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    result_json = Column(Text, nullable=False)  # JSON 字符串
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, server_default=func.now()
    )

    # 关系
    project = relationship("Project", back_populates="organize_results")

    def __repr__(self) -> str:
        return f"<OrganizeResult id={self.id} project_id={self.project_id}>"


class OutlineTemplate(Base):
    """大纲模板表 —— 预设/自定义的大纲结构模板。"""

    __tablename__ = "outline_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    description = Column(Text, default="")
    structure_json = Column(Text, nullable=False)  # JSON 字符串，定义章节结构
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, server_default=func.now()
    )

    # 关系
    outline_results = relationship("OutlineResult", back_populates="template")

    def __repr__(self) -> str:
        return f"<OutlineTemplate id={self.id} name={self.name!r}>"


class OutlineResult(Base):
    """大纲生成结果表 —— 按模板为项目生成的大纲内容。"""

    __tablename__ = "outline_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id = Column(
        Integer,
        ForeignKey("outline_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    result_json = Column(Text, nullable=False)  # JSON 字符串
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, server_default=func.now()
    )

    # 关系
    project = relationship("Project", back_populates="outline_results")
    template = relationship("OutlineTemplate", back_populates="outline_results")

    def __repr__(self) -> str:
        return f"<OutlineResult id={self.id} project_id={self.project_id}>"
