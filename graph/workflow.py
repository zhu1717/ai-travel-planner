from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from graph.nodes import parser_node, plan_node, search_node, validation_node
from graph.state import TravelAgentState


def build_travel_graph():
    """构建旅行规划工作流。"""

    graph_builder = StateGraph(TravelAgentState) #StateGraph是 LangGraph 里的核心类。创建一个状态图对象，用于构建旅行规划工作流。

#添加处理站：add_node
    graph_builder.add_node("parser", parser_node)#把你在 nodes.py 里写好的函数注册到图中。你给它起了一个名字（比如 "parser"），后面就可以通过这个名字来编排流程。
    graph_builder.add_node("search", search_node)
    graph_builder.add_node("plan", plan_node)
    graph_builder.add_node("validate", validation_node)

#定义传输线：add_edge
    graph_builder.add_edge(START, "parser") #这是流程的“物理连线”。它规定了数据流向：parser 做完之后，必须交给 search 去处理。
    graph_builder.add_edge("parser", "search")
    graph_builder.add_edge("search", "plan")
    graph_builder.add_edge("plan", "validate")
    graph_builder.add_edge("validate", END)

    return graph_builder.compile()
#这行代码是最后的“封装”。它会检查你的流程是否连通，有没有死循环，有没有孤立的节点。一旦编译成功，你就得到了一个可执行的智能体（Agent）。