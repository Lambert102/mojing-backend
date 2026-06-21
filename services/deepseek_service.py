"""DeepSeek 服务 —— 统一 LLM 调用，强制 JSON 输出。

提供两个核心能力：
1. 梳理（organize）：分析卡片集合，返回叙事结构、人物、伏笔
2. 大纲生成（generate_outline）：按模板结构生成大纲章节
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
        if not self._api_key:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置，请检查 .env 文件")

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
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


# 全局单例
deepseek_service = DeepSeekService()
