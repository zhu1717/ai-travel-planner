from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    """所有数据模型的公共基类。"""

    model_config = ConfigDict(extra="forbid")


class TravelInput(StrictBaseModel):
    city: str = Field(..., description="目标旅行城市")
    days: int = Field(..., ge=1, le=7, description="出行天数")
    budget: int | None = Field(default=None, ge=0, description="总预算")
    preferences: list[str] = Field(default_factory=list, description="偏好标签")
    travel_style: Literal["轻松", "适中", "紧凑"] = Field(
        default="轻松",
        description="旅行节奏，会影响每日安排密度",
    )
    start_date: str | None = Field(default=None, description="出发日期，格式 YYYY-MM-DD")
#后端只会接受这种格式的input

class GeoPoint(StrictBaseModel):
    lat: float = Field(default=0.0, description="纬度")
    lng: float = Field(default=0.0, description="经度")


class SourceItem(StrictBaseModel):
    title: str = Field(default="", description="来源标题")
    url: str = Field(default="", description="来源链接")
    content: str = Field(default="", description="来源摘要")


class WeatherInfo(StrictBaseModel):
    date: str | None = Field(default=None, description="天气日期")
    condition: str = Field(default="", description="天气情况")
    temperature_range: str = Field(default="", description="温度区间")
    travel_advice: str = Field(default="", description="出行建议")
    source: list[SourceItem] = Field(default_factory=list, description="天气来源")


class CandidatePOI(StrictBaseModel):
    name: str = Field(..., description="POI 名称")
    address: str = Field(default="", description="标准地址")
    city: str = Field(default="", description="所属城市")
    district: str = Field(default="", description="所属区县")
    location: GeoPoint = Field(default_factory=GeoPoint, description="经纬度")
    poi_id: str | None = Field(default=None, description="高德 POI ID")
    category: str = Field(default="", description="POI 分类")
    source_name: str = Field(default="amap", description="来源名称")


class PlanItem(StrictBaseModel):
    name: str = Field(..., description="行程项名称")
    type: Literal["attraction", "food", "transport", "rest", "shopping", "other"] = Field(
        default="other",
        description="行程项类型",
    )
    start_time: str = Field(default="", description="开始时间，格式 HH:MM")
    end_time: str = Field(default="", description="结束时间，格式 HH:MM")
    address: str = Field(default="", description="标准地址")
    location: GeoPoint = Field(default_factory=GeoPoint, description="经纬度")
    reason: str = Field(default="", description="推荐原因")
    source: list[SourceItem] = Field(default_factory=list, description="参考来源")


class DayPlan(StrictBaseModel):
    day: int = Field(..., ge=1, description="第几天")
    date: str | None = Field(default=None, description="日期，格式 YYYY-MM-DD")
    theme: str = Field(default="", description="当日主题")
    weather: WeatherInfo | None = Field(default=None, description="当日天气")
    items: list[PlanItem] = Field(default_factory=list, description="当天安排")


class ValidationResult(StrictBaseModel):
    passed: bool = Field(default=True, description="是否通过校验")
    issues: list[str] = Field(default_factory=list, description="发现的问题列表")


class SearchResults(StrictBaseModel):
    attractions: list[CandidatePOI] = Field(default_factory=list, description="景点候选")
    foods: list[CandidatePOI] = Field(default_factory=list, description="美食候选")
    web_sources: list[SourceItem] = Field(default_factory=list, description="网页检索结果")
    weather: list[WeatherInfo] = Field(default_factory=list, description="天气结果")


class TravelPlan(StrictBaseModel):
    city: str = Field(..., description="旅行城市")
    days: int = Field(..., ge=1, description="旅行天数")
    summary: str = Field(default="", description="行程摘要")
    itinerary: list[DayPlan] = Field(default_factory=list, description="逐日行程")
    validation: ValidationResult = Field(default_factory=ValidationResult, description="校验结果")
