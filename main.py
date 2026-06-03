from __future__ import annotations

import argparse
import json
from pathlib import Path

from graph.state import build_initial_state
from graph.workflow import build_travel_graph
from models.schemas import TravelInput
from services.amap_service import AmapService
from services.tavily_service import TavilyService
from services.weather_service import WeatherService


OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
#Path(__file__)：获取当前运行文件（main.py）的路径。
#.resolve()：解析出该文件的绝对路径（防止路径含糊不清）。
#.parent：获取当前文件所在的文件夹路径（即整个项目的根目录）。
#/ "outputs"：在根目录下拼接出一个名为 outputs 的文件夹路径。

def build_sample_input() -> TravelInput:
    return TravelInput(
        city="武汉",
        days=2,
        budget=2000,
        preferences=["美食", "景点"],
        travel_style="轻松",
        start_date="2026-06-10",
    )


def ensure_output_dir() -> None:#“防御性文件操作”，其目的是将 Agent 处理好的结果（比如旅行计划）保存到电脑硬盘上。
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
#确保“输出目录”存在。如果它不存在，就自动创建它。

def save_json(filename: str, payload: dict) -> Path:#将一个字典（payload）变成一个漂亮的 JSON 文件存进硬盘。
    ensure_output_dir()# 调用上面的函数，保证保存之前文件夹是存在的。
    file_path = OUTPUT_DIR / filename
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        # json.dumps：把 Python 字典转换成 JSON 字符串。
        # ensure_ascii=False：非常关键，这保证了换成 JSON 字符时，中文字符能正常显示，不会变成乱码(\u4e2d...)。
        # indent=2：给输出的 JSON 增加缩进，使其具备良好的可读性（美观排版）。
        encoding="utf-8",#当我把这串字符写入硬盘成文件时，请用 UTF-8 格式进行编码，确保中文字符不乱码，这是现代开发的标准格式。
    )
    # json.dumps：把 Python 字典转换成 JSON 字符串。
    # ensure_ascii=False：非常关键，这保证了中文字符能正常显示，不会变成乱码(\u4e2d...)。
    # indent=2：给输出的 JSON 增加缩进，使其具备良好的可读性（美观排版）。
    return file_path

#一下四个choice是对应mode的四种模式
def test_amap(city: str) -> None:
    service = AmapService()
    results = service.search_poi(keyword="景点", city=city, page_size=5)
    print(f"\n[AMAP] {city} POI 搜索结果：")#\n是换行符
    print(results)
    for poi in results[:3]:#“只取列表里的前 3 个元素”。
        print(
            f"- {poi.name} | {poi.address} | "
            f"({poi.location.lat}, {poi.location.lng})"
        )


def test_tavily(city: str) -> None:
    service = TavilyService()
    results = service.search_travel_references(city=city, preferences=["博物馆", "火锅"])
    print(f"\n[TAVILY] {city} 检索结果：")
    for item in results[:3]:
        print(f"- {item.title} | {item.url}")


def test_weather(city: str, days: int) -> None:
    service = WeatherService()
    results = service.get_forecast(city=city, days=days)
    print(f"\n[WEATHER] {city} 天气结果：")
    for item in results:
        print(f"- {item.date} | {item.condition} | {item.temperature_range}")

#给 Agent 提供初始信息，让它在预设好的“逻辑流程图”中跑完全程，最后把结果存入文件。
#重新看，目前还没看workflow文件，看不懂
def run_graph() -> None:
    travel_input = build_sample_input()
    initial_state = build_initial_state(travel_input)#创建TravelAgentState类的实例
    graph = build_travel_graph()

    result = graph.invoke(initial_state)
    #注入数据：将你的 initial_state（那个装满信息的“记事本”）交给引擎。
    #寻找起点：引擎会根据你的定义（graph_builder.add_edge(START, "parser")），自动找到第一个要执行的节点（parser）。对应notes.py文件的def parser_node，接受初始状态initial_state作为参数。（一般第一个node都要接受intial state）
    #左边的变量result接收notes.py里面所有节点的输出return。
    final_plan = result["final_plan"]#final_plan是validation_node的输出
    payload = final_plan.model_dump() if hasattr(final_plan, "model_dump") else final_plan
    #hasattr(obj, "属性名")，用于判断对象是否拥有某个属性或方法。检查 final_plan 这个对象里有没有 model_dump 这个方法，如果有，就执行转换；如果没有，就直接返回 final_plan。
    #model_dump：把一个 Pydantic 模型实例（对象）转换成普通 Python 数据结构（通常是 dict）。
    #假如final_plan 这个对象里没有 model_dump 这个方法，说明它可能已经是我想要的格式了。直接输出
    file_path = save_json("travel_plan.json", payload)
    errors = result.get("errors", [])

    print("\n[GRAPH] 工作流执行完成。")
    print(f"输出文件：{file_path}")
    if errors:
        print("\n[DEBUG] 本次运行记录到以下错误或回退信息：")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))#可视化


def parse_args() -> argparse.Namespace:#argparse.Namespace是一个类，用于创建一个命名对象，用于存储命令行参数。
    parser = argparse.ArgumentParser(description="AI 旅行规划系统调试入口")#终端输入python main.py --help后会显示帮助信息：AI 旅行规划系统调试入口
    parser.add_argument(
        "--mode",#让用户在命令行中指定调试的模式。例如:python main.py --mode test_weather
        choices=["test_amap", "test_tavily", "test_weather", "run_graph"],
        default="run_graph",#假如用户没有指定mode，则mode默认=run_graph
        help="""运行模式：
        test_amap     测试高德地图接口
        test_tavily   测试 Tavily 搜索接口
        test_weather  测试天气接口
        run_graph     运行完整旅行规划流程""",  
    )
    parser.add_argument(
        "--city",
        default="西安",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="天气调试或样例输入的天数",
    )
    return parser.parse_args()
#规定了当用户从命令行启动程序时，
#允许输入哪些参数？
#这些参数是什么类型？
#默认值是什么？
#合法取值有哪些？
#帮助信息怎么显示？

def main() -> None:
    args = parse_args()

    if args.mode == "test_amap":
        test_amap(args.city)
        return
    if args.mode == "test_tavily":
        test_tavily(args.city)
        return
    if args.mode == "test_weather":
        test_weather(args.city, args.days)
        return
    run_graph()


if __name__ == "__main__":#如果 __name__ 的值等于 "__main__"。__name__ 是 Python 自动给当前模块（文件）的一个名字，运行python main.py的时候，变量 __name__ 的值变成了 "__main__"
    main()
