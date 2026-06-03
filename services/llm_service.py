from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from models.schemas import SearchResults, TravelInput, TravelPlan

load_dotenv()


DEFAULT_MODEL = "qwen3.7-max"


class LLMStageError(ValueError):
    """携带失败阶段信息的异常。"""

    def __init__(
        self,
        stage: str,
        detail: str,
        *,
        attempt: int,
        raw_preview: str = "",
    ) -> None:
        self.stage = stage
        self.detail = detail
        self.attempt = attempt
        self.raw_preview = raw_preview

        message = f"[阶段: {stage}] [第 {attempt} 次尝试] {detail}"
        if raw_preview:
            message += f"\n[原始片段] {raw_preview}"
        super().__init__(message)


class LLMService:
    """阿里云百炼兼容 OpenAI 接口的轻量封装。"""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        if not self.api_key:
            raise ValueError("缺少 DASHSCOPE_API_KEY，请先在 .env 中配置阿里云百炼密钥。")

        self.model_name = model_name
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    @staticmethod
    def build_plan_prompt(
        travel_input: TravelInput,
        search_results: SearchResults,
    ) -> str:
        """构造规划节点使用的 Prompt。"""

        input_payload = travel_input.model_dump(mode="json")
        search_payload = search_results.model_dump(mode="json")
    #它的作用是把一个复杂的 Python 数据类实例，变成一个标准的 JSON 格式字典。方便大模型查看和理解。


        return f"""
你是一个严谨的旅行规划助手。请根据用户需求、候选景点/美食、天气信息，生成一个严格符合要求的旅行计划 JSON。

【用户输入】
{json.dumps(input_payload, ensure_ascii=False, indent=2)}

【搜索结果】
{json.dumps(search_payload, ensure_ascii=False, indent=2)}

【输出要求】
1. 只能输出 JSON，不要输出解释文字，不要输出 Markdown 代码块。
2. 顶层字段必须包含：city, days, summary, itinerary, validation。
3. itinerary 是数组，每一天必须包含：day, date, theme, weather, items。
4. items 中每个元素必须包含：name, type, start_time, end_time, address, location, reason, source。
5. type 只能从以下枚举中选择：attraction, food, transport, rest, shopping, other。
6. 每天安排 2 到 4 个项目，优先兼顾景点和美食，不要只排博物馆。
7. 必须尽量使用搜索结果里已经提供的地址和经纬度，不要编造不存在的地点。
8. 如果天气有雨，尽量安排室内或移动距离较短的项目。
9. validation 字段先输出为：{{"passed": true, "issues": []}}。
10. 所有 items[*].source 必须是数组，不能是字符串。没有来源时也必须写成 []，绝对不能写成 "amap"。
11. weather.source 也必须是数组，元素格式为 {{ "title": "", "url": "", "content": "" }}。

【额外约束】
1. 如果用户 travel_style 是“轻松”，每天安排2个项目。
2. 如果用户 travel_style 是“适中”，安排 3 个左右项目。
3. 如果用户 travel_style 是“紧凑”，安排4 个项目，但不要时间重叠。
4. 尽量避免同一天地点相距过远。
5. 日期优先使用 start_date 逐日递增。

【source 字段示例】
错误示例：
"source": "amap"

正确示例：
"source": []

或：
"source": [
  {{
    "title": "高德地图",
    "url": "https://lbs.amap.com/",
    "content": "POI 来源"
  }}
]

请直接返回最终 JSON。
""".strip()
#json.dumps 是 Python 的标准库函数，它的全称是 JSON Dump String（把 JSON 数据 dump 成字符串）。
#.strip()为了保证最后拼接出来的、发送给大模型的 Prompt 是干净、紧凑的纯文本，不带有任何无意义的头部或尾部空行。

    @staticmethod
    def _extract_json_text(content: str) -> str:
        """从模型响应中提取 JSON 文本。"""

        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("模型返回内容中未找到合法 JSON。")
        return text[start : end + 1]

    def generate_plan_text(self, prompt: str, temperature: float = 0.2) -> str:
        """调用模型并返回原始文本。"""

        response = self.client.chat.completions.create(
            model=self.model_name,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个严格遵守 JSON 输出格式的旅行规划助手。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("模型未返回任何内容。")
        return content

    @staticmethod
    def _normalize_source_value(value: Any) -> list[dict[str, str]]:
        """将 source 字段统一纠偏成 SourceItem 数组格式。"""

        if value is None or value == "":
            return []

        if isinstance(value, str):
            return [
                {
                    "title": value,
                    "url": "",
                    "content": "",
                }
            ]

        if isinstance(value, dict):
            return [
                {
                    "title": str(value.get("title", "")),
                    "url": str(value.get("url", "")),
                    "content": str(value.get("content", "")),
                }
            ]

        if isinstance(value, list):
            normalized_items: list[dict[str, str]] = []
            for item in value:
                if isinstance(item, str):
                    normalized_items.append(
                        {
                            "title": item,
                            "url": "",
                            "content": "",
                        }
                    )
                elif isinstance(item, dict):
                    normalized_items.append(
                        {
                            "title": str(item.get("title", "")),
                            "url": str(item.get("url", "")),
                            "content": str(item.get("content", "")),
                        }
                    )
            return normalized_items

        return []

    @classmethod
    def _normalize_plan_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """在 Pydantic 校验前，对模型输出做最小纠偏。"""

        itinerary = payload.get("itinerary", [])
        if not isinstance(itinerary, list):
            return payload

        for day in itinerary:
            if not isinstance(day, dict):
                continue

            weather = day.get("weather")
            if isinstance(weather, dict):
                weather["source"] = cls._normalize_source_value(weather.get("source", []))

            items = day.get("items", [])
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                item["source"] = cls._normalize_source_value(item.get("source", []))

        return payload

    def generate_plan_json(
        self,
        travel_input: TravelInput,
        search_results: SearchResults,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """生成行程 JSON，并在解析失败时做简单重试。"""

        base_prompt = self.build_plan_prompt(travel_input, search_results)
        retry_hints = [
            "",
            "\n\n上一次输出不符合要求。请补全缺失字段，并严格按照 JSON 返回。",
            "\n\n不要输出任何解释文字、不要输出 Markdown，只输出一个可被 json.loads() 解析的 JSON 对象。",
        ]

        last_error: Exception | None = None
        for attempt in range(max_retries):
            prompt = base_prompt + retry_hints[min(attempt, len(retry_hints) - 1)]
            attempt_no = attempt + 1

            try:
                content = self.generate_plan_text(prompt)
            except Exception as exc:
                last_error = LLMStageError(
                    "model_call",
                    f"模型调用失败：{exc}",
                    attempt=attempt_no,
                )
                continue

            try:
                json_text = self._extract_json_text(content)
            except Exception as exc:
                last_error = LLMStageError(
                    "extract_json",
                    f"无法从模型输出中提取 JSON：{exc}",
                    attempt=attempt_no,
                    raw_preview=content[:500],
                )
                continue

            try:
                payload = json.loads(json_text)
            except Exception as exc:
                last_error = LLMStageError(
                    "json_loads",
                    f"JSON 解析失败：{exc}",
                    attempt=attempt_no,
                    raw_preview=json_text[:500],
                )
                continue

            payload = self._normalize_plan_payload(payload)

            try:
                TravelPlan.model_validate(payload)
            except Exception as exc:
                last_error = LLMStageError(
                    "pydantic_validate",
                    f"TravelPlan 结构校验失败：{exc}",
                    attempt=attempt_no,
                    raw_preview=json.dumps(payload, ensure_ascii=False)[:500],
                )
                continue

            return payload

        if last_error is None:
            raise ValueError("模型生成失败，且未返回可追踪错误。")
        raise ValueError(f"模型生成 JSON 失败：{last_error}") from last_error
