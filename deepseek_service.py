"""DeepSeek 服务 —— 统一 LLM 调用，强制 JSON 输出。

提供三个核心能力：
1. 梳理（organize）：分析卡片集合，返回叙事结构、人物、伏笔
2. 大纲生成（generate_outline）：按模板结构生成大纲章节
3. 角色扮演对话（roleplay_chat）：以角色身份与作者对话
"""

import json
from typing import Any, Optional

import httpx

from config import settings

# ─── 梳理 Prompt ────────────────────────────────────────

ORGANIZE_SYSTEM_PROMPT = """你是一位资深的小说编辑和故事架构师。你的任务是分析用户提供的故事卡片，提取以下结构化信息：

1. **narrative_structure**（叙事结构）：分析故事的整体叙事脉络，包括：
   - 开篇设定（exposition）
   - 激励事件（inciting_incident）
   - 发展（rising_action）
   - 高潮（climax）
   - 结局（resolution）

2. **characters**（人物）：列出所有人物及其关系网络，每个角色包含：
   - name：角色名
   - role：在故事中的角色定位
   - traits：性格特征
   - motivation：动机/目标
   - relationships：与其他角色的关系

3. **foreshadowing**（伏笔）：识别所有已埋下的伏笔和线索：
   - description：伏笔描述
   - related_cards：关联的卡片标题
   - suggested_payoff：建议的回收方式

请严格以 JSON 格式输出，不要包含任何其他文字。"""

# ─── 大纲生成 Prompt ────────────────────────────────────

OUTLINE_SYSTEM_PROMPT = """你是一位专业的小说大纲规划师。你需要根据用户提供的故事梳理结果和大纲模板结构，生成一份完整的小说章节大纲。

要求：
1. 严格按照模板中定义的章节结构生成
2. 每个章节包含：章节标题、核心冲突、关键事件、涉及人物
3. 章节之间需要有因果逻辑链
4. 考虑伏笔的埋设与回收时机

请严格以 JSON 格式输出，结构如下：
{
  "chapters": [
    {
      "number": 1,
      "title": "章节标题",
      "core_conflict": "核心冲突描述",
      "key_events": ["事件1", "事件2"],
      "characters_involved": ["角色1", "角色2"],
      "foreshadowing_planted": ["埋下的伏笔"],
      "foreshadowing_resolved": ["回收的伏笔"]
    }
  ],
  "summary": "大纲总体概述"
}"""

# ─── 角色扮演 System Prompt 模板 ───────────────────────

ROLEPLAY_SYSTEM_PROMPT_TEMPLATE = """你是一个角色扮演引擎。你将扮演一个小说角色，根据角色设定与作者对话。

## 你的角色
- 姓名：{name}
- 表面人设（别人眼中的你）：{surface_persona}
- 实际人设（真实的你）：{actual_persona}
- 外貌特征：{appearance}
- 性格特点：{personality}
- 成长线索：{growth_arc}
- 人物关系：{relationships}
- 功能定位：{functional_role}

## 核心规则
1. 始终以角色的身份、口吻和思维模式说话，不要跳出角色。
2. 你的回答要基于"实际人设"——这是角色的真实面貌，但在对话中可以适当体现"表面人设"对外界的伪装。
3. 语言风格要符合古言设定，用词文雅但有角色个性。
4. 不要说"作为一个AI""根据设定"等元话语。
5. 回答控制在200字以内，像真人对话一样自然。
6. 如果作者问你剧情走向或角色想法，从角色的视角给出真实的反应。"""


# ─── DeepSeek 客户端 ────────────────────────────────────

class DeepSeekService:
    """DeepSeek API 服务封装。

    通过 OpenAI 兼容接口调用 deepseek-chat 模型。
    """

    def __init__(self) -> None:
        self._base_url: str = settings.DEEPSEEK_BASE_URL
        self._api_key: str = settings.DEEPSEEK_API_KEY
        self._model: str = settings.DEEPSEEK_MODEL
        self._timeout: float = 120.0

    async def _chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """统一的聊天补全调用。

        Args:
            system_prompt: 系统角色提示词。
            user_message: 用户消息。
            temperature: 生成温度，越低越确定。
            max_tokens: 最大输出 token 数。

        Returns:
            模型返回的文本内容。

        Raises:
            RuntimeError: API 调用失败时。
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        return await self._chat_messages(messages, temperature, max_tokens)

    async def _chat_messages(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """底层聊天补全调用，接受完整的 messages 数组。

        Args:
            messages: 消息列表，每项包含 role 和 content。
            temperature: 生成温度，越低越确定。
            max_tokens: 最大输出 token 数。

        Returns:
            模型返回的文本内容。

        Raises:
            RuntimeError: API 调用失败时。
        """
        if not self._api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置，请检查 .env 文件")

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"DeepSeek API 错误 ({response.status_code}): {response.text}"
                )

            data: dict = response.json()
            content: str = data["choices"][0]["message"]["content"]
            return content

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从模型输出中提取 JSON 对象。

        能够处理被 markdown 代码块包裹的 JSON。
        """
        text = text.strip()
        # 去掉可能的 markdown 代码块标记
        if text.startswith("```"):
            # 找到第一个换行后的内容
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)

    # ─── 业务方法 ────────────────────────────────────────

    async def organize(
        self, cards_data: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """梳理卡片：分析故事元素。

        Args:
            cards_data: 卡片列表，每个元素包含 title, content, type。

        Returns:
            包含 narrative_structure, characters, foreshadowing 的字典。
        """
        # 构建用户消息
        cards_text = json.dumps(cards_data, ensure_ascii=False, indent=2)
        user_message = f"请分析以下故事卡片，提取叙事结构、人物和伏笔：\n\n{cards_text}"

        raw_response = await self._chat(
            system_prompt=ORGANIZE_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.5,
            max_tokens=4096,
        )

        return self._extract_json(raw_response)

    async def generate_outline(
        self,
        organize_result: dict[str, Any],
        template_structure: dict[str, Any],
        cards_data: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """按模板生成大纲。

        Args:
            organize_result: 梳理结果 JSON。
            template_structure: 模板结构 JSON。
            cards_data: 原始卡片数据。

        Returns:
            包含 chapters 和 summary 的大纲 JSON。
        """
        user_parts: list[str] = [
            "请根据以下信息生成小说大纲：",
            "",
            "## 梳理结果",
            json.dumps(organize_result, ensure_ascii=False, indent=2),
            "",
            "## 大纲模板结构",
            json.dumps(template_structure, ensure_ascii=False, indent=2),
            "",
            "## 原始卡片",
            json.dumps(cards_data, ensure_ascii=False, indent=2),
        ]
        user_message = "\n".join(user_parts)

        raw_response = await self._chat(
            system_prompt=OUTLINE_SYSTEM_PROMPT,
            user_message=user_message,
            temperature=0.7,
            max_tokens=8192,
        )

        return self._extract_json(raw_response)

    async def roleplay_chat(
        self,
        character_card: Any,
        messages: list[dict[str, str]],
        user_message: str,
    ) -> str:
        """角色扮演对话：以角色身份与作者对话。

        Args:
            character_card: CharacterCard ORM 实例，包含角色的各字段。
            messages: 历史消息列表，每项包含 role 和 content。
            user_message: 用户最新消息内容。

        Returns:
            AI 角色扮演回复字符串。
        """
        # 构建 system prompt
        system_prompt = ROLEPLAY_SYSTEM_PROMPT_TEMPLATE.format(
            name=character_card.name,
            surface_persona=character_card.surface_persona or "（未设定）",
            actual_persona=character_card.actual_persona or "（未设定）",
            appearance=character_card.appearance or "（未设定）",
            personality=character_card.personality or "（未设定）",
            growth_arc=character_card.growth_arc or "（未设定）",
            relationships=character_card.relationships or "（未设定）",
            functional_role=character_card.functional_role or "（未设定）",
        )

        # 构建完整的 messages 数组
        api_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        # 追加历史消息
        for msg in messages:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

        # 追加当前用户消息
        api_messages.append({"role": "user", "content": user_message})

        return await self._chat_messages(api_messages, temperature=0.8, max_tokens=512)


# 全局单例
deepseek_service = DeepSeekService()
