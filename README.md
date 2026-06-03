# 基于 LangGraph 多智能体协作的 AI 旅行规划系统

## 1. 项目定位

本项目是一个基于 `LangGraph` 的多节点协作式 AI 旅行规划系统，目标是在较短周期内完成一个可运行、可演示、可扩展的最小闭环版本。

项目核心价值不在于堆叠大量 Agent 数量，而在于：

- 使用 `LangGraph` 组织清晰的任务流转
- 使用真实世界工具补齐大模型的时效性短板
- 使用地图坐标和地理信息提升行程的可执行性
- 使用结构化校验降低幻觉和无效输出

当前版本优先聚焦后端能力，不包含前端页面。

## 2. 项目目标

输入一份结构化旅行需求，系统自动：

- 检索当前真实世界信息
- 查询景点或餐厅的标准地址与经纬度
- 生成按天拆分的旅行行程
- 补充每日天气信息
- 对输出结果进行结构化校验
- 在必要时触发自动修正

## 3. 项目范围

### 当前阶段保留

- 单城市旅行规划
- 2\~3 天行程
- 景点 + 餐饮安排
- Tavily 网络检索
- 高德地图 POI / 地理编码
- 结构化 JSON 输出
- Python/Pydantic 规则校验

### 当前阶段暂不实现

- 前端页面
- 多城市联动
- 酒店和机票预订
- 精细预算拆分
- 地图可视化界面
- 复杂用户账户系统

## 4. 系统架构

项目采用 `4 节点` 设计，但并不是 `4 个纯 LLM Agent`，而是将适合规则处理的部分下沉到 Python 节点。

```text
[结构化用户输入]
   │
   ▼
1. parser_node
   - 当前方案：直接用 Python 接收结构化参数
   - 不走 LLM，避免不必要的调用成本
   │
   ▼
2. search_node
   - 纯 Python 节点
   - 调用 Tavily 和高德 API
   - 获取候选景点、餐厅、POI、经纬度、地址、网页摘要、天气信息
   │
   ▼
3. plan_node
   - 强模型节点
   - 根据用户约束、搜索结果、地理信息生成初版行程 JSON
   │
   ▼
4. validation_node
   - 混合节点
   - 先用 Python / Pydantic 校验
   - 若存在缺失、冲突或不合理安排，再调用强模型修正
```

## 5. 模型分工

推荐遵循以下思路：

- `search_node` 不使用大模型，全部走 Python + HTTP 请求
- `plan_node` 使用最强模型，负责统筹生成行程草案
- `validation_node` 优先走规则校验，仅在失败时触发强模型修正

这样的好处是：

- 降低 token 成本
- 降低幻觉风险
- 提高输出可控性
- 更容易在 5 天内完成调试

## 6. 工具选型

### Tavily Search API

用途：

- 获取真实世界的网页信息
- 弥补大模型无法实时感知当前世界状态的问题
- 用于补充景点、美食、近期公告、出行提醒等文本信息

适合负责：

- 热门景点和美食候选检索
- 近期攻略或注意事项
- 与天气、营业、临时变化相关的网页信息收集

说明：

- Tavily 更适合做网页事实补充，不等于官方权威数据库
- 若后续时间允许，天气可以升级为专门天气 API

### 高德开放平台 API

用途：

- 将景点或餐厅名称标准化为 POI
- 获取绝对经纬度和官方地址
- 为后续路线排序和距离控制提供可靠地理基础

适合负责：

- POI 搜索
- 地理编码 / 逆地理编码
- 距离或路线相关能力

## 7. 输入格式

当前项目不再使用自然语言解析作为第一阶段必要能力，而是直接采用结构化输入。

示例：

```json
{
  "city": "西安",
  "days": 3,
  "budget": 2000,
  "preferences": ["历史", "美食"],
  "travel_style": "轻松",
  "start_date": "2026-06-10"
}
```

字段说明：

- `city`: 目标城市
- `days`: 出行天数
- `budget`: 总预算
- `preferences`: 偏好标签
- `travel_style`: 旅行节奏，如轻松、紧凑
- `start_date`: 出发日期

## 8. 输出格式

输出采用结构化 JSON，便于：

- 程序校验
- 二次导出为  PDF/MarkDown
- 后续接入前端或数据库

示例：

```json
{
  "city": "西安",
  "days": 3,
  "summary": "适合历史文化与美食偏好的轻松行程",
  "itinerary": [
    {
      "day": 1,
      "date": "2026-06-10",
      "theme": "城墙与回民街",
      "weather": {
        "condition": "晴",
        "temperature_range": "22-31C",
        "travel_advice": "白天适合步行游览，注意防晒补水",
        "source": []
      },
      "items": [
        {
          "name": "西安城墙",
          "type": "attraction",
          "start_time": "09:00",
          "end_time": "11:30",
          "address": "",
          "location": {
            "lat": 0,
            "lng": 0
          },
          "reason": "历史地标，适合作为首日核心景点",
          "source": []
        }
      ]
    }
  ],
  "validation": {
    "passed": true,
    "issues": []
  }
}
```

说明：

- `weather` 以“每天一份”的方式放在 `itinerary[].weather`
- `source` 建议保留来源信息，方便解释结果来源

## 9. 状态设计

建议 LangGraph 的共享状态包含以下字段：

```python
state = {
    "user_query": "",
    "parsed_input": {},
    "search_results": {},
    "candidate_pois": [],
    "draft_plan": {},
    "validation_result": {},
    "final_plan": {}
}
```

可按需要逐步扩展：

- `sources`
- `errors`
- `iteration_count`
- `messages`

## 10. 校验规则

当前阶段建议至少实现以下规则：

- 必须有 `city`
- 必须有 `days`
- 每天至少 `2~4` 个安排
- 每个安排必须有 `name/address/lat/lng`
- 相邻地点不能跨城
- 单天总时长不能过长
- 景点重复出现时要报错

后续可继续补充：

- 时间重叠检测
- 同一天总移动距离过长
- 餐饮和景点类别过于单一
- 天气与安排冲突

## 11. 为什么第一天不先接高德和 Tavily

第一天的核心目标不是“把 API 调通”，而是“把项目边界、数据结构、节点职责和校验规则彻底定死”。

原因：

- 如果输入输出结构还没定，第二天调回来的 API 数据很容易无处安放
- 如果状态设计没定，LangGraph 节点流转会反复推翻
- 如果校验规则没定，强模型提示词也会不断返工

因此，第一天允许使用占位值或模拟值。

例如：

- `address` 可暂时为空字符串
- `lat/lng` 可临时使用 `0`
- `weather` 可先保留空结构或模拟文本
- `source` 可先为空数组

第二天再把这些占位字段替换成真实 API 返回结果。

## 12. 五天开发计划

### Day 1：设计定稿

目标：

- 固定项目范围
- 固定输入结构
- 固定输出 JSON
- 固定节点职责
- 固定状态设计
- 固定校验规则

产出：

- 本 README
- 输入样例
- 输出样例
- 节点与状态说明

### Day 2：工具接入

目标：

- 单独调通 Tavily
- 单独调通高德
- 明确 API 返回格式
- 将返回结果映射到项目统一字段

重点验证：

- Tavily 是否能返回足够干净的文本摘要
- 高德是否能稳定返回 POI、地址、经纬度
- 天气数据最终走哪条通路更稳定

### Day 3：LangGraph 主流程搭建

目标：

- 串联 `search_node -> plan_node -> validation_node`
- 跑通最小闭环
- 输出初版 itinerary JSON

### Day 4：校验与重规划

目标：

- 接入 Pydantic 校验
- 对不合法结果进行自动修正
- 增强地理顺路性和去重逻辑

### Day 5：演示打磨

目标：

- 准备 2\~3 个稳定案例
- 导出 Markdown 行程单
- 整理汇报材料和项目亮点

## 13. 目录建议

建议逐步整理为如下结构：

```text
travel_agent/
├── .env
├── README.md
├── requirements.txt
├── main.py
├── graph/
│   ├── state.py（定义全局状态）
│   ├── nodes.py
│   └── workflow.py（重要，学习怎么写）
├── services/
│   ├── tavily_service.py
│   ├── amap_service.py
│   └── weather_service.py
├── models/
│   └── schemas.py（输出字段，供pydantic检查）
└── outputs/
```

## 14. 环境变量

当前项目需要的环境变量包括：

```bash
DASHSCOPE_API_KEY=your_key
TAVILY_API_KEY=your_key
AMAP_KEY=your_key
```

建议：

- 不要把真实密钥提交到公开仓库
- 若仓库曾提交过真实密钥，应尽快轮换密钥

## 15. 当前结论

本项目当前采用的策略是：

- 输入直接走结构化参数
- 搜索和地图查询全部使用 Python 工具节点
- 强模型专注于规划与修正
- 输出采用可校验、可扩展的 JSON 结构

这是一个非常适合在 `5 天` 内完成最小闭环复现的实现路径。
