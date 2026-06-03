from __future__ import annotations

import os

from dotenv import load_dotenv
from tavily import TavilyClient

from models.schemas import SourceItem

load_dotenv()


class TavilyService:
    """对 Tavily 搜索能力做轻量封装。"""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        if not self.api_key:
            raise ValueError("缺少 TAVILY_API_KEY，请先在 .env 中配置 Tavily Key。")
        self.client = TavilyClient(api_key=self.api_key)#初始化TavilyClient，传入api_key

#主要函数
    def search(
        self,
        query: str,#这是你真正想搜索的问题。
        *,#它要求你在调用 search 函数时，必须显式写出参数名。（针对*下面所有参数）。如果你调用时只写 search("西安", "general")，程序会报错。你必须写成 search("西安", topic="general")。这是为了让代码逻辑更清晰，防止你填错参数的位置。
        topic: str = "general",#general 代表通用搜索。给你最全面、最杂的搜索结果（包含新闻、博客、官网、百科等）。除此之外，"news"（新闻搜索）
        max_results: int = 5,
    ) -> list[SourceItem]:
        """执行搜索并返回统一格式的来源列表。"""

        response = self.client.search(#上文已经定义了self.client=TavilyClient(api_key=self.api_key),这里的search是TavilyClient类的方法，用于执行搜索。
            query=query,
            topic=topic,
            max_results=max_results,
            search_depth="advanced",#搜索深度，advanced表示高级搜索，basic表示基本搜索。
            include_answer=True,#如果不加这个参数，你只会得到一堆零散的网页链接和摘录；加上它，Tavily 内部集成的 AI 模型就会帮你把这些信息“嚼碎”，直接给你一个总结好的结论。
        )

        items: list[SourceItem] = []#列表里的每一个元素都必须是一个 SourceItem 实例。
        answer = response.get("answer", "")#answer 永远只有一个（也就是 AI 帮你总结的那一段话），而 max_results 控制的是“搜索来源的数量”。
        if answer:
            items.append(#append它是 Python 列表的“吞入”动作，用于将一个元素添加到列表的末尾。
                SourceItem(
                    title="Tavily Answer",
                    url="",#留空原因：它不是从某个具体的网页爬取下来的，而是由 Tavily 的 AI 模型“凭空归纳”出来的。既然它没有对应的网页来源，也就没有所谓的“网址（URL）”。
                    content=answer,
                )
            )

        for result in response.get("results", []):#results是一个列表，里面总共有5个元素（max_results=5），result会遍历5个元素。
            items.append(
                SourceItem(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    content=result.get("content", ""),
                )
            )
        return items#最终items会包含第一个answer和5个result。

    def search_travel_references(self, city: str, preferences: list[str]) -> list[SourceItem]:
        """搜索一个城市的旅行参考信息。"""
    #这个函数的作用是让参数更加精简，仅需传递city和preferences，而不需要传递topic和max_results。就可以去搜索了
    #如果用户没有传递preferences，默认搜索景点、美食、攻略。
        keywords = "、".join(preferences) if preferences else "景点 美食 攻略"#它会把列表里的每一个元素取出来，中间用“分隔符”连在一起，变成一个长字符串。举例：假设 preferences = ["景点", "美食"]，"、".join(preferences) 的结果就是 "景点、美食"。
        query = f"{city} 旅游攻略 {keywords}"
        return self.search(query, topic="general", max_results=6)#self.search是调用了search函数
