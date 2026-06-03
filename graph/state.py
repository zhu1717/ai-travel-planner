from __future__ import annotations

from typing import Any, TypedDict

from models.schemas import (
    CandidatePOI,
    SearchResults,
    SourceItem,
    TravelInput,
    TravelPlan,
    ValidationResult,
)


class TravelAgentState(TypedDict, total=False):
    """LangGraph 在节点间共享的状态。"""

    # 用户原始输入。
    # 当前项目采用结构化输入时，这里可以留空；
    # 如果以后改成自然语言输入，这里就保存用户最初说的话。
    user_query: str

    # parser_node 的输出，也是后续所有节点最核心的输入。
    # 它保存经过校验和标准化后的旅行参数，例如城市、天数、预算、偏好等。
    parsed_input: TravelInput | dict[str, Any]

    # search_node 的输出。
    # 保存统一整理后的搜索结果，里面通常包含景点候选、美食候选、天气信息、网页来源等。
    search_results: SearchResults | dict[str, Any]

    # search_node 从高德等工具中提取出的 POI 列表。
    # 这是更“地点级”的数据，给 plan_node 做排序、筛选、组装行程时使用。
    candidate_pois: list[CandidatePOI]

    # plan_node 的输出。
    # 表示“初版行程草案”，通常还没有经过最终质检，后面还要交给 validation_node 校验。
    draft_plan: TravelPlan | dict[str, Any]

    # validation_node 的直接输出。
    # 只保存校验结果本身，例如是否通过、发现了哪些问题。
    validation_result: ValidationResult | dict[str, Any]

    # validation_node 校验并修正后的最终结果。
    # 如果流程正常结束，main.py 最终通常就是读取这个字段做导出或展示。
    final_plan: TravelPlan | dict[str, Any]

    # search_node 收集到的网页来源列表。
    # 后续可以给大模型提供参考，也可以在最终结果里保留引用来源。
    sources: list[SourceItem]

    # 流程运行过程中记录的错误信息。
    # 某个节点调用失败、校验失败或接口报错时，可以把报错文本写到这里，方便排查。
    errors: list[str]

    # 当前工作流已经执行到第几轮。
    # 如果以后加入“校验失败 -> 回退重规划”的循环，这个字段就能用来限制最大重试次数。
    iteration_count: int


def build_initial_state(travel_input: TravelInput) -> TravelAgentState:
    """为图执行构造一份初始状态。"""

    return TravelAgentState(
        user_query="",
        parsed_input=travel_input,
        search_results={},
        candidate_pois=[],
        draft_plan={},
        validation_result={},
        final_plan={},
        sources=[],
        errors=[],
        iteration_count=0,
    )
