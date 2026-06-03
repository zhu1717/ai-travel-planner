# AI Travel Planner

基于 `LangGraph` 多节点工作流的 AI 旅行规划系统，面向“城市 + 天数 + 预算 + 偏好 + 出行风格”这类结构化输入，自动生成带有天气、POI 地址、经纬度和来源信息的旅行行程。

本项目参考了 `LangGraph` 官方多智能体工作流示例，并结合旅行规划场景进行了二次设计与实现。系统将“大模型规划能力”和“真实世界工具调用”结合起来，尽量减少纯文本幻觉，提升行程的可执行性。

## 项目亮点

- 使用 `LangGraph` 编排旅行规划流程，包含解析、搜索、规划、校验四个核心节点
- 接入 `Tavily Search API` 获取实时旅游攻略、景点与美食相关网页信息
- 接入 `高德开放平台 API` 获取 POI 标准地址、经纬度和天气信息
- 使用 `Pydantic` 约束输入输出 Schema，确保大模型输出可被程序校验
- 在 `plan_node` 中接入阿里云百炼模型，失败时自动回退到规则版规划逻辑
- 输出结构化 JSON，便于后续扩展前端、Markdown/PDF 导出或继续做自动重规划

## 功能概览

当前版本已经支持：

- 根据结构化输入生成多日旅行规划
- 查询景点、美食、购物等候选地点
- 生成包含 `address`、`lat/lng`、`source` 的行程项
- 生成每日天气信息与简单出行建议
- 对最终行程执行基础业务校验
- 将结果保存到 `outputs/travel_plan.json`

## 项目结构

```text
ai-travel-planner/
├── .env.example
├── .gitignore
├── README.md
├── check_api.py
├── main.py
├── requirements.txt
├── graph/
│   ├── nodes.py
│   ├── state.py
│   └── workflow.py
├── models/
│   └── schemas.py
├── services/
│   ├── amap_service.py
│   ├── llm_service.py
│   ├── tavily_service.py
│   └── weather_service.py
└── outputs/
    └── travel_plan.json
```

各目录职责如下：

- `main.py`：统一调试入口，支持单独测试服务或运行完整工作流
- `graph/`：LangGraph 状态定义、节点逻辑和工作流编排
- `services/`：第三方 API 封装，包括阿里云百炼、高德、Tavily、天气服务
- `models/`：Pydantic 数据模型，约束输入、输出和中间结构
- `outputs/`：保存结构化旅行规划结果

## 工作流设计

系统当前采用 4 个核心节点：

1. `parser_node`
   - 接收结构化输入
   - 校验并整理为标准 `TravelInput`
2. `search_node`
   - 调用 Tavily 获取旅游参考信息
   - 调用高德获取 POI、地址、经纬度和天气
3. `plan_node`
   - 调用阿里云百炼模型生成旅行 JSON
   - 如果模型输出不合法，则回退到规则版计划生成
4. `validation_node`
   - 校验时间、字段完整性、重复项等业务规则
   - 输出最终 `final_plan`

## 输入格式

当前 `run_graph` 采用结构化输入，示例格式如下：

```json
{
  "city": "武汉",
  "days": 2,
  "budget": 2000,
  "preferences": ["美食", "景点"],
  "travel_style": "轻松",
  "start_date": "2026-06-10"
}
```

字段说明：

- `city`：旅行城市
- `days`：旅行天数
- `budget`：预算，当前主要作为上下文信息
- `preferences`：偏好标签，例如 `美食`、`景点`、`逛街`、`博物馆`
- `travel_style`：推荐使用 `轻松`、`适中`、`紧凑`
- `start_date`：行程起始日期

## 输出格式

程序会生成结构化 JSON，主要字段包括：

- `city`
- `days`
- `summary`
- `itinerary`
- `validation`

其中 `itinerary` 中的每一天都包含：

- `day`
- `date`
- `theme`
- `weather`
- `items`

其中 `items` 中的每个行程项都包含：

- `name`
- `type`
- `start_time`
- `end_time`
- `address`
- `location`
- `reason`
- `source`

## 环境准备

建议使用 `Python 3.11+`。

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
copy .env.example .env
```

然后在 `.env` 中填入你自己的 API Key：

```env
DASHSCOPE_API_KEY="your_dashscope_api_key"
TAVILY_API_KEY="your_tavily_api_key"
AMAP_KEY="your_amap_key"
```

说明：

- `DASHSCOPE_API_KEY`：阿里云百炼模型调用密钥
- `TAVILY_API_KEY`：联网搜索密钥
- `AMAP_KEY`：高德开放平台 Web 服务 Key

## 运行方式

### 1. 测试阿里云模型连通性

```bash
python check_api.py
```

### 2. 单独测试高德 POI

```bash
python main.py --mode test_amap --city 武汉
```

### 3. 单独测试 Tavily 搜索

```bash
python main.py --mode test_tavily --city 武汉
```

### 4. 单独测试天气

```bash
python main.py --mode test_weather --city 武汉 --days 2
```

### 5. 运行完整工作流

```bash
python main.py --mode run_graph
```

运行完成后，结果会保存到：

```text
outputs/travel_plan.json
```

## 当前调试方式说明

当前版本中，`run_graph` 使用 `main.py` 里的 `build_sample_input()` 作为固定样例输入。

如果你想快速测试不同案例，可以直接修改 `build_sample_input()` 中的字段，例如：

- `city`
- `days`
- `preferences`
- `travel_style`
- `start_date`

这是一种面向开发调试的写法，适合快速对比不同城市和偏好下的输出效果。后续如果继续迭代，可以把 `run_graph` 改成支持命令行完整输入。

## 示例场景

当前项目已经测试过多组输入，例如：

- `西安 + 3天 + 历史/美食`
- `成都 + 2天 + 博物馆/火锅`
- `广州 + 4天 + 美食/逛街`
- `武汉 + 2天 + 美食/景点`

这些测试说明系统已经具备：

- 多城市切换能力
- 多偏好切换能力
- 不同出行风格下的节奏调整能力
- 行程生成后的结构化校验能力

## 已知限制

当前版本仍有一些可继续优化的地方：

- `weather.date` 在少数城市案例下可能存在映射不稳定的情况
- 个别地点虽然结构合法，但仍可能需要进一步加强“必须来自候选 POI”的约束
- `validation_node` 当前会指出问题，但尚未完全实现“校验失败后自动回到 plan_node 重规划”
- `run_graph` 仍主要依赖固定样例输入，不是正式接口形态
- 当前仓库默认输出 JSON，PDF 导出能力尚未单独整理为独立模块

## 适合继续扩展的方向

- 增加 `PDF` 或 `Markdown` 导出
- 增加“校验失败自动重规划”闭环
- 限制模型只能使用候选 POI，进一步降低地址幻觉
- 为 `run_graph` 增加完整命令行参数输入
- 增加简单前端或 Web 界面

## 安全说明

- 请不要把真实 `.env` 文件上传到公开仓库
- 请不要在代码或截图中暴露 API Key
- 建议公开仓库仅保留 `.env.example`

## 项目定位

这是一个面向“多智能体 / LLM 应用工程”方向的后端原型项目，重点不在于做一个成熟旅游产品，而在于展示以下能力：

- LangGraph 工作流设计
- 大模型与工具调用结合
- 第三方 API 封装
- 结构化输出与 Schema 校验
- 面向真实场景的调试与失败回退机制

如果你正在查看这个仓库，欢迎直接 clone 后按上述步骤配置 API Key 运行。
