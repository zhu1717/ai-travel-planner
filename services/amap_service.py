from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

from models.schemas import CandidatePOI, GeoPoint

load_dotenv()
#把 .env 里的所有密钥，直接注入到当前运行的“整个操作系统进程的环境变量

class AmapService:
    """对高德 Web 服务 API 的轻量封装。"""

    BASE_URL = "https://restapi.amap.com/v3"

    def __init__(self, api_key: str | None = None, timeout: int = 15) -> None:
        self.api_key = api_key or os.getenv("AMAP_KEY", "")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("缺少 AMAP_KEY，请先在 .env 中配置高德 Key。")

    def _get(self, endpoint: str, params: dict) -> dict:
        request_params = {**params, "key": self.api_key}
        response = requests.get(
            f"{self.BASE_URL}{endpoint}",#拼成完整的URL地址
            params=request_params,
            timeout=self.timeout,
        )#会按照地址f""，要获取的地址以及key，用requests发给高德，get获得返回的信息，打包给response
        response.raise_for_status()#自动报警，一旦检测到 404、500 等网络错误，它会在一微秒内拉响大楼火警，瞬间让整个程序熔断。

        data = response.json()
        if data.get("status") != "1":
            message = data.get("info") or data.get("infocode") or "高德接口调用失败"
            raise ValueError(message)
        return data

    @staticmethod #如果这个函数调用了这个类里面的其他函数或者变量，就需要用self，但是如果不需要的话，就可以用@（只对紧随其后的“下一个” def 有效）
    def _parse_location(raw_location: str) -> GeoPoint:#为后面定义别的函数铺垫，把经纬度字符串转换为 GeoPoint 对象
        if not raw_location or "," not in raw_location:
            return GeoPoint()

        lng, lat = raw_location.split(",", maxsplit=1)
        return GeoPoint(lat=float(lat), lng=float(lng))#GeoPoint实例化，返回一个GeoPoint对象，包含lat度和lng度两个属性



#这个是主要的发挥中心作用的函数
    def search_poi(#该函数负责根据关键词向高德接口发起查询，获取原始地点数据，并将其清洗、转换为系统统一的 CandidatePOI 标准积木，通过经纬度切分与字段过滤，确保旅行 Agent 后续逻辑使用时数据格式规范且安全
        self,
        keyword: str,#会用类似“大雁塔”“火锅”“钟楼附近的酒店”这样的参数
        city: str,
        page_size: int = 10,#单次获取的景点数量上限
        city_limit: bool = True,#严格限制在当前城市内，系统默认把这个开关设置为“开启（真）”状态
    ) -> list[CandidatePOI]:
        """根据关键词搜索 POI。"""

        data = self._get(#用前面定义的类 def _get(self, endpoint: str, params: dict) -> dict
            "/place/text",
            {
                "keywords": keyword,
                "city": city,
                "citylimit": "true" if city_limit else "false",
                "offset": page_size,
                "page": 1,#高德地图的搜索接口通常不支持无限长的数据一次性返回，所以它把数据切成了很多“页”。page: 1 意味着我们永远只看搜索结果中的“第一页”数据。
                "extensions": "base",#高德支持两种模式base和all，选择base基础版
            },
        )#_get 拿回一个大字典data，里面包含了所有搜索结果的详细信息。

        results: list[CandidatePOI] = []#这个变量 results 接下来只能用来装 CandidatePOI 类型的积木，而且它本质上是一个列表（list）。右半部分 = []：这是真实的初始化动作。它在内存里真正创建了一个空的列表，并把 results 这个名字指向了这个空列表。
        for poi in data.get("pois", []):#_get 拿回来的大字典里，提取那个存满景点信息的“pois”列表。如果里面什么都没有，就返回一个空列表 []，防止程序崩溃。
            results.append(
                CandidatePOI(#schemas.py 里的 CandidatePOI 类型，用来存储景点信息
                    name=poi.get("name", ""),#""是（空字符串）：是“兜底默认值”。
                    address=poi.get("address", ""),#类似“东四环中路189号百盛北门”
                    city=str(poi.get("cityname", "")),
                    district=poi.get("adname", ""),#区县级别的返回
                    location=self._parse_location(poi.get("location", "")),#调用前面定义的函数
                    poi_id=poi.get("id"),#某个地点的唯一标识符
                    category=poi.get("type", ""),
                    source_name="amap",#定死了信息来自“amap”
                )
            )
        return results

    def geocode(self, address: str, city: str | None = None) -> GeoPoint | None:
        """将地址解析为经纬度。"""
    #接收地址与可选城市名，调用高德地理编码接口，将文本地址转换为标准 GeoPoint 经纬度坐标，解析失败则返回 None。
        params = {"address": address} #字典创建与赋值写法，"address": address是键值对
        if city:
            params["city"] = city #字典增加一对键值对

        data = self._get("/geocode/geo", params)#注意这里的data并不是和get函数里面的data是一个东西，get函数根据endpoint="/geocode/geo"（/geocode/geo 是高德地图开放平台提供的地理编码服务的专属接口路径（API Endpoint），告诉具体地址，返回formatted_address，adcode，province等信息）去取得信息后，给了data并且return data，这里把data的数据赋值给了左边data
        geocodes = data.get("geocodes", [])#这里的get是获取信息的手段，而不是函数_get，如果没有则赋值[]
        if not geocodes:
            return None
        return self._parse_location(geocodes[0].get("location", ""))

    def get_city_adcode(self, city: str) -> str | None:
        """将城市名称解析为 adcode，供天气接口等场景使用。"""

        data = self._get("/geocode/geo", {"address": city})
        geocodes = data.get("geocodes", [])
        if not geocodes:
            return None
        return geocodes[0].get("adcode")
    #adcode 是“行政区划代码”的缩写，你可以把它理解为中国每一个行政区域的“身份证号”。根据adcode，高德地图或天气接口就能一秒钟锁定目标