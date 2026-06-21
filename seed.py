"""种子数据模块 —— 预置 3 个大纲模板，启动时自动插入（幂等操作）。"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import OutlineTemplate

# ─── 预设模板定义 ────────────────────────────────────────

PRESET_TEMPLATES: list[dict] = [
    {
        "name": "经典三幕",
        "description": "好莱坞经典三幕式结构，适用于大多数叙事作品，强调冲突的建立、发展和解决。",
        "structure_json": json.dumps(
            {
                "structure": "三幕式",
                "acts": [
                    {
                        "act": 1,
                        "name": "建置",
                        "description": "介绍主角、世界观和核心冲突的萌芽。",
                        "typical_ratio": "25%",
                        "suggested_chapters": 3,
                        "key_elements": [
                            "开篇钩子",
                            "日常世界展示",
                            "激励事件",
                            "主角做出决定",
                        ],
                    },
                    {
                        "act": 2,
                        "name": "对抗",
                        "description": "冲突升级，主角遭遇重重阻碍，逐渐成长。",
                        "typical_ratio": "50%",
                        "suggested_chapters": 6,
                        "key_elements": [
                            "上升行动",
                            "中点转折",
                            "黑暗时刻",
                            "新的希望",
                        ],
                    },
                    {
                        "act": 3,
                        "name": "解决",
                        "description": "最终对决与结局，所有伏笔回收。",
                        "typical_ratio": "25%",
                        "suggested_chapters": 3,
                        "key_elements": [
                            "高潮对决",
                            "结局",
                            "尾声",
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "起承转合",
        "description": "东亚传统叙事结构，强调情绪的渐进与转折，适合注重人物内心成长的故事。",
        "structure_json": json.dumps(
            {
                "structure": "起承转合",
                "parts": [
                    {
                        "part": 1,
                        "name": "起（起笔）",
                        "description": "引入背景与人物，铺垫故事基调。",
                        "suggested_chapters": 2,
                        "key_elements": [
                            "场景描绘",
                            "人物初登场",
                            "氛围营造",
                            "情节铺垫",
                        ],
                    },
                    {
                        "part": 2,
                        "name": "承（承接）",
                        "description": "发展剧情，深化人物关系与矛盾。",
                        "suggested_chapters": 4,
                        "key_elements": [
                            "矛盾展开",
                            "人物互动",
                            "支线发展",
                            "情感积累",
                        ],
                    },
                    {
                        "part": 3,
                        "name": "转（转折）",
                        "description": "局势突变，揭示真相或重大变故。",
                        "suggested_chapters": 3,
                        "key_elements": [
                            "关键转折事件",
                            "真相揭露",
                            "人物抉择",
                            "情绪爆发点",
                        ],
                    },
                    {
                        "part": 4,
                        "name": "合（收合）",
                        "description": "余韵悠长的收束，留下回味空间。",
                        "suggested_chapters": 2,
                        "key_elements": [
                            "结局收束",
                            "人物归宿",
                            "主题升华",
                            "余韵留白",
                        ],
                    },
                ],
            },
            ensure_ascii=False,
        ),
    },
    {
        "name": "剧情树",
        "description": "多线分支叙事结构，适合群像剧或拥有复杂世界观的作品，允许多条故事线交织发展。",
        "structure_json": json.dumps(
            {
                "structure": "剧情树",
                "trunk": {
                    "name": "主线干",
                    "description": "贯穿始终的核心剧情线",
                    "suggested_chapters": 4,
                    "key_elements": [
                        "核心冲突",
                        "主线推进节点",
                    ],
                },
                "branches": [
                    {
                        "branch": "A",
                        "name": "主角成长线",
                        "description": "主角个人能力与心智的成长轨迹",
                        "suggested_chapters": 3,
                    },
                    {
                        "branch": "B",
                        "name": "感情/友情线",
                        "description": "重要人物间的情感关系发展",
                        "suggested_chapters": 2,
                    },
                    {
                        "branch": "C",
                        "name": "世界观揭秘线",
                        "description": "逐步揭示世界背后隐藏的真相",
                        "suggested_chapters": 2,
                    },
                ],
                "intersections": [
                    {
                        "name": "交汇点",
                        "description": "各条支线与主线交汇的关键节点",
                        "suggested_count": 3,
                    },
                ],
            },
            ensure_ascii=False,
        ),
    },
]


async def seed_templates(db: AsyncSession) -> None:
    """如果模板不存在则插入预设的 3 个大纲模板（幂等操作）。"""
    for tmpl in PRESET_TEMPLATES:
        # 检查是否已存在（按名称去重）
        existing = await db.execute(
            select(OutlineTemplate).where(OutlineTemplate.name == tmpl["name"])
        )
        if existing.scalar_one_or_none() is None:
            template = OutlineTemplate(
                name=tmpl["name"],
                description=tmpl["description"],
                structure_json=tmpl["structure_json"],
            )
            db.add(template)
