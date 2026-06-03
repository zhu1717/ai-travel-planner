from __future__ import annotations

from datetime import datetime, timedelta

from graph.state import TravelAgentState
from models.schemas import (
    CandidatePOI,
    DayPlan,
    PlanItem,
    SearchResults,
    TravelInput,
    TravelPlan,
    ValidationResult,
)
from services.amap_service import AmapService
from services.llm_service import LLMService
from services.tavily_service import TavilyService
from services.weather_service import WeatherService


DEFAULT_ATTRACTION_KEYWORDS = ["景点", "博物馆", "历史景点"]
DEFAULT_FOOD_KEYWORDS = ["美食", "特色餐厅", "小吃"]
STYLE_ITEM_LIMITS = {
    "轻松": 2,
    "适中": 3,
    "紧凑": 4,
}

#检验输入的raw_input是否符合TravelInput的实例
def _ensure_travel_input(raw_input: TravelInput | dict) -> TravelInput:
    if isinstance(raw_input, TravelInput):#isinstance(对象, 类名)，它会返回一个布尔值（True 或 False），判断某个“对象”是不是属于某个“类”的实例。
        return raw_input
    return TravelInput.model_validate(raw_input)#model_validate：是 Pydantic 提供的方法，用于将普通字典转换为模型实例。
    #如果字典里的数据有问题，model_validate 会直接抛出一个 ValidationError（验证错误），程序会立刻停止并告知你哪里出错了。

#根据你填写的“出发日期”和“旅行天数”，自动帮你推算出每一天的具体日期。
def _build_dates(start_date: str | None, days: int) -> list[str | None]:
    if not start_date:
        return [None] * days#如果没有出发日期，就返回一个包含 None 个元素的列表。

    base_date = datetime.strptime(start_date, "%Y-%m-%d").date()#按照YYYY-MM-DD格式解析日期，对输入的字符串类型的start_date转化为Python 可识别的日期对象。date()是只保留年月日，不包含时分秒。
    return [(base_date + timedelta(days=index)).isoformat() for index in range(days)]
#range(days)：创建一个从 0 到 days-1 的序列。如果天数是 3，它就是 0, 1, 2。
#index 从 0 开始，一直递增到 days - 1
#timedelta(days=index)：这是 Python 的“时间差”对象。当 index 为 0 时，差 0 天；为 1 时，差 1 天……
#base_date + timedelta(...)：日期加法。比如 6月10日 + 1天 = 6月11日。
#.isoformat()：把计算出来的日期对象再次变回标准的字符串格式（"2026-06-10"）。
#如果输入 start_date="2026-06-01" 且 days=3，函数 _build_dates 会返回一个包含 3 个日期字符串的列表（List）：['2026-06-01', '2026-06-02', '2026-06-03']

#去除搜索结果中重复的景点（POI）
#在调用高德地图 API 进行搜索时，有时候因为关键词的重叠（比如同时搜索“博物馆”和“历史景点”），同一个景点可能会被多次返回。这个函数就是为了确保最终的行程清单里，同一个地点不会出现两次。
def _deduplicate_pois(pois: list[CandidatePOI]) -> list[CandidatePOI]:
    seen: set[tuple[str, str]] = set()#这行代码创建了一个名叫 seen 的空箱子，专门用来存放我们“已经见过的景点”。因为是 set(数据类型：用于创建包含无序且唯一元素的数据结构)，所以即便你试图往里加重复的东西，它也会自动帮你过滤掉。
    unique_items: list[CandidatePOI] = []
    for poi in pois:
        key = (poi.name, poi.address)
        if key in seen:
            continue#立即结束本次循环的剩余部分，直接跳到循环的下一次迭代
        seen.add(key)
        unique_items.append(poi)
    return unique_items


def _search_pois(
    amap_service: AmapService,
    city: str,
    keywords: list[str],
    page_size: int = 5,
) -> list[CandidatePOI]:
    results: list[CandidatePOI] = []
    for keyword in keywords:
        try:
            results.extend(
                amap_service.search_poi(
                    keyword=keyword,
                    city=city,
                    page_size=page_size,
                )
            )
        except Exception:
            continue
    return _deduplicate_pois(results)


def parser_node(state: TravelAgentState) -> TravelAgentState:
    """结构化输入模式下，仅做参数校验和标准化。"""

    travel_input = _ensure_travel_input(state.get("parsed_input", {}))
    return {
        "parsed_input": travel_input,
        "errors": [],
    }

#重点
def search_node(state: TravelAgentState) -> TravelAgentState:
    """收集网页信息、POI 信息和天气信息。"""

    travel_input = _ensure_travel_input(state["parsed_input"])
    amap_service = AmapService()
    tavily_service = TavilyService()
    weather_service = WeatherService()

    preference_keywords = travel_input.preferences or []
    attraction_keywords = preference_keywords + DEFAULT_ATTRACTION_KEYWORDS#DEFAULT_ATTRACTION_KEYWORDS = ["景点", "博物馆", "历史景点"]
    food_keywords = preference_keywords + DEFAULT_FOOD_KEYWORDS#DEFAULT_FOOD_KEYWORDS = ["美食", "特色餐厅", "小吃"]

    attractions = _search_pois(amap_service, travel_input.city, attraction_keywords)
    foods = _search_pois(amap_service, travel_input.city, food_keywords)

    web_sources = tavily_service.search_travel_references(
        city=travel_input.city,
        preferences=travel_input.preferences,
    )
    weather = weather_service.get_forecast(
        city=travel_input.city,
        days=travel_input.days,
    )

    search_results = SearchResults(
        attractions=attractions[: max(travel_input.days * 2, 4)],
        foods=foods[: max(travel_input.days * 2, 4)],
        web_sources=web_sources,
        weather=weather,
    )

    return {
        "search_results": search_results,
        "candidate_pois": [*search_results.attractions, *search_results.foods],
        "sources": search_results.web_sources,
    }


def _infer_theme(preferences: list[str], day_index: int) -> str:
    if preferences:
        joined = " / ".join(preferences[:2])
        return f"{joined} 第 {day_index} 天主题"
    return f"城市探索第 {day_index} 天"


def _plan_item_from_poi(
    poi: CandidatePOI,
    *,
    item_type: str,
    start_time: str,
    end_time: str,
    reason: str,
) -> PlanItem:
    return PlanItem(
        name=poi.name,
        type=item_type,
        start_time=start_time,
        end_time=end_time,
        address=poi.address,
        location=poi.location,
        reason=reason,
        source=[],
    )


def _build_day_items(
    attractions: list[CandidatePOI],
    foods: list[CandidatePOI],
    *,
    day_index: int,
    item_limit: int,
) -> list[PlanItem]:
    items: list[PlanItem] = []

    attraction_start = day_index * 2
    food_start = day_index * 2

    if len(attractions) > attraction_start:
        items.append(
            _plan_item_from_poi(
                attractions[attraction_start],
                item_type="attraction",
                start_time="09:00",
                end_time="11:30",
                reason="上午优先安排核心景点，便于进入旅行状态。",
            )
        )

    if len(foods) > food_start:
        items.append(
            _plan_item_from_poi(
                foods[food_start],
                item_type="food",
                start_time="12:00",
                end_time="13:30",
                reason="中午安排当地餐饮体验，减少往返折返。",
            )
        )

    if len(attractions) > attraction_start + 1:
        items.append(
            _plan_item_from_poi(
                attractions[attraction_start + 1],
                item_type="attraction",
                start_time="14:30",
                end_time="17:00",
                reason="下午继续安排同城景点，保持节奏稳定。",
            )
        )

    if item_limit >= 4 and len(foods) > food_start + 1:
        items.append(
            _plan_item_from_poi(
                foods[food_start + 1],
                item_type="food",
                start_time="18:00",
                end_time="19:30",
                reason="晚间安排补充美食体验，方便形成完整的一天行程。",
            )
        )

    return items

def _build_rule_based_plan(
    travel_input: TravelInput,
    search_results: SearchResults,
) -> TravelPlan:
    """当模型调用失败时，回退到规则版行程生成。"""

    item_limit = STYLE_ITEM_LIMITS.get(travel_input.travel_style, 3)
    dates = _build_dates(travel_input.start_date, travel_input.days)

    itinerary: list[DayPlan] = []
    for day in range(1, travel_input.days + 1):
        day_items = _build_day_items(#它在循环生成每一天的具体安排
            search_results.attractions,
            search_results.foods,
            day_index=day - 1,
            item_limit=item_limit,
        )
        weather = search_results.weather[day - 1] if len(search_results.weather) >= day else None
        itinerary.append(
            DayPlan(
                day=day,
                date=dates[day - 1],
                theme=_infer_theme(travel_input.preferences, day),
                weather=weather,
                items=day_items,
            )
        )

    draft_plan = TravelPlan(
        city=travel_input.city,
        days=travel_input.days,
        summary=f"为 {travel_input.city} 生成的 {travel_input.travel_style} 型 {travel_input.days} 天旅行规划（规则回退版）。",
        itinerary=itinerary,
        validation=ValidationResult(passed=True, issues=[]),
    )
    return draft_plan


#重点
def plan_node(state: TravelAgentState) -> TravelAgentState:#这个参数 state 的数据结构必须是 TravelAgentState 类定义的格式。
    """优先调用阿里云模型生成行程草案，失败时回退到规则版。"""

    travel_input = _ensure_travel_input(state["parsed_input"])
    search_results = SearchResults.model_validate(state["search_results"])
#search_results是上面定义的serch_node节点的输出存进去的数据，同时也是在state.py文件里面的类属性：search_results: SearchResults | dict[str, Any]
#state["search_results"] 的意思就是：“从这个全局共享的记事本（State）中，取出名为 search_results 的那个数据块。（通过记事本（State）传递状态！！！）
#SearchResults是schemas.py里面的Pydantic 类，用于定义搜索结果的结构。
#model_validate方法是pydantic提供的一个方法，用于将一个字典转换为一个pydantic模型对象。
#这段话的含义就是：哪怕 state["search_results"] 里现在存的只是一个普通的字典，请按照 SearchResults 这个类的结构，把它重新验证并转换为一个结构严谨的对象。

    errors = list(state.get("errors", []))
    try:
        llm_service = LLMService()
        plan_json = llm_service.generate_plan_json(travel_input, search_results)
        draft_plan = TravelPlan.model_validate(plan_json)
    except Exception as exc:
        errors.append(f"plan_node 模型生成失败，已回退到规则版：{exc}")
        draft_plan = _build_rule_based_plan(travel_input, search_results)

    return {
        "draft_plan": draft_plan,
        "errors": errors,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def _time_to_minutes(value: str) -> int | None:
    if not value:
        return None
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _repair_day_items(items: list[PlanItem]) -> list[PlanItem]:
    unique_items: list[PlanItem] = []
    seen_names: set[str] = set()
    for item in items:
        if item.name in seen_names:
            continue
        seen_names.add(item.name)
        unique_items.append(item)
    return unique_items[:4]

#重点
def validation_node(state: TravelAgentState) -> TravelAgentState:
    """执行基础规则校验，并对少量问题做自动修复。"""

    draft_plan = TravelPlan.model_validate(state["draft_plan"])
    issues: list[str] = []
    existing_errors = list(state.get("errors", []))

    if not draft_plan.city:
        issues.append("缺少 city。")
    if not draft_plan.days:
        issues.append("缺少 days。")

    repaired_itinerary: list[DayPlan] = []
    seen_names: set[str] = set()

    for day_plan in draft_plan.itinerary:
        repaired_items = _repair_day_items(day_plan.items)

        if len(repaired_items) < 2 or len(repaired_items) > 4:
            issues.append(f"Day {day_plan.day} 的安排数量不在 2~4 之间。")

        last_end: int | None = None
        for item in repaired_items:
            if not item.name or not item.address:
                issues.append(f"Day {day_plan.day} 存在缺少名称或地址的行程项。")
            if item.location.lat == 0 or item.location.lng == 0:
                issues.append(f"Day {day_plan.day} 存在缺少经纬度的行程项。")
            if item.name in seen_names:
                issues.append(f"景点或餐厅 `{item.name}` 重复出现。")
            seen_names.add(item.name)

            start_minutes = _time_to_minutes(item.start_time)
            end_minutes = _time_to_minutes(item.end_time)
            if start_minutes is not None and end_minutes is not None:
                if end_minutes <= start_minutes:
                    issues.append(f"Day {day_plan.day} 的 `{item.name}` 时间区间无效。")
                if last_end is not None and start_minutes < last_end:
                    issues.append(f"Day {day_plan.day} 存在时间重叠。")
                last_end = end_minutes

        if repaired_items:
            first_start = _time_to_minutes(repaired_items[0].start_time)
            last_end = _time_to_minutes(repaired_items[-1].end_time)
            if first_start is not None and last_end is not None and last_end - first_start > 12 * 60:
                issues.append(f"Day {day_plan.day} 总时长过长。")

        repaired_itinerary.append(
            DayPlan(
                day=day_plan.day,
                date=day_plan.date,
                theme=day_plan.theme,
                weather=day_plan.weather,
                items=repaired_items,
            )
        )

    validation = ValidationResult(
        passed=len(issues) == 0,
        issues=issues,
    )

    final_plan = TravelPlan(
        city=draft_plan.city,
        days=draft_plan.days,
        summary=draft_plan.summary,
        itinerary=repaired_itinerary,
        validation=validation,
    )

    return {
        "validation_result": validation,
        "final_plan": final_plan,
        "errors": existing_errors + issues,
    }
