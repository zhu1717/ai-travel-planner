from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

from models.schemas import SourceItem, WeatherInfo
from services.amap_service import AmapService

load_dotenv()


class WeatherService:
    """使用高德天气接口获取未来几天的天气。"""

    BASE_URL = "https://restapi.amap.com/v3/weather/weatherInfo"

    def __init__(self, api_key: str | None = None, timeout: int = 15) -> None:
        self.api_key = api_key or os.getenv("AMAP_KEY", "")
        self.timeout = timeout
        self.amap_service = AmapService(api_key=self.api_key, timeout=timeout)
        if not self.api_key:
            raise ValueError("缺少 AMAP_KEY，请先在 .env 中配置高德 Key。")

    def _get_forecast_payload(self, city: str) -> list[dict]:
        adcode = self.amap_service.get_city_adcode(city)
        if not adcode:
            raise ValueError(f"无法为城市 `{city}` 获取 adcode。")

        response = requests.get(
            self.BASE_URL,
            params={
                "key": self.api_key,
                "city": adcode,
                "extensions": "all",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()#data是dict格式{}
        if data.get("status") != "1":
            message = data.get("info") or data.get("infocode") or "高德天气接口调用失败"
            raise ValueError(message)

        forecasts = data.get("forecasts", [])#左边的forecasts是list格式[]
        if not forecasts:
            return []
        return forecasts[0].get("casts", [])

    @staticmethod
    def _build_advice(day_weather: str, night_weather: str) -> str:
        weather_text = f"{day_weather} {night_weather}"
        if "雨" in weather_text:
            return "建议携带雨具，优先安排室内或移动距离较短的行程。"
        if "高温" in weather_text or "晴" in weather_text:
            return "白天适合步行游览，注意防晒和补水。"
        if "雪" in weather_text or "寒" in weather_text:
            return "注意保暖，尽量减少过长时间的室外停留。"
        return "天气整体适中，可按常规节奏安排行程。"#它会在所有前面的 if 条件都不满足时被触发。

#主要函数
    def get_forecast(self, city: str, days: int = 3) -> list[WeatherInfo]:
        """返回未来几天的天气信息。"""

        casts = self._get_forecast_payload(city)
        results: list[WeatherInfo] = []#results出现的效果：[WeatherInfo( date="2026-05-29",condition="晴/晴",temperature_range="15-30℃",travel_advice="白天适合步行游览，注意防晒和补水。",source=[]),, # 第1个实例对象。。。]
        for cast in casts[:days]:
            day_weather = cast.get("dayweather", "")
            night_weather = cast.get("nightweather", "")
            temp_range = f"{cast.get('nighttemp', '')}-{cast.get('daytemp', '')}C"
            results.append(
                WeatherInfo(
                    date=cast.get("date"),
                    condition=f"{day_weather} / {night_weather}".strip(" /"),#效果：晴/雨。strip(" /")的作用移除字符串开头和结尾的特定字符。
                    temperature_range=temp_range,
                    travel_advice=self._build_advice(day_weather, night_weather),
                    source=[
                        SourceItem(
                            title="高德天气预报",
                            url="https://lbs.amap.com/",
                            content=f"{city} {cast.get('date', '')} 天气预报",
                        )
                    ],
                )
            )
        return results
