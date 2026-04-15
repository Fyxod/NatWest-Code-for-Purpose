from langgraph.graph import END, StateGraph

from agent.graph_nodes import (
    chart_skill_node,
    excel_skill_node,
    failure,
    generate,
    retriever,
    main_router,
    summary_router,
    web_search,
    document_summarizer,
    global_summarizer,
    self_knowledge,
    sql_query_node,
)
from agent.state import AgentState
from core.constants import *


# Building the state graph
graph_builder = StateGraph(AgentState)

# Add nodes
graph_builder.add_node(RETRIEVER, retriever)
graph_builder.add_node(GENERATE, generate)
graph_builder.add_node(ROUTER, main_router)
graph_builder.add_node(WEB_SEARCH, web_search)
graph_builder.add_node(ANSWER, lambda state: END)
graph_builder.add_node(FAILURE, failure)
graph_builder.add_node(DOCUMENT_SUMMARIZER, document_summarizer)
graph_builder.add_node(GLOBAL_SUMMARIZER, global_summarizer)
graph_builder.add_node(SELF_KNOWLEDGE, self_knowledge)
graph_builder.add_node(SQL_QUERY, sql_query_node)
graph_builder.add_node(EXCEL_CREATE, excel_skill_node)
graph_builder.add_node(CHART_CREATE, chart_skill_node)

# Set the entry point
graph_builder.set_entry_point(RETRIEVER)

# Define edges
# Retrieval now flows directly to generation.
graph_builder.add_edge(RETRIEVER, GENERATE)

# Conditional edges from GENERATE via router
graph_builder.add_conditional_edges(
    GENERATE,
    main_router,
    {
        ANSWER: END,
        WEB_SEARCH: WEB_SEARCH,
        DOCUMENT_SUMMARIZER: DOCUMENT_SUMMARIZER,
        GLOBAL_SUMMARIZER: GLOBAL_SUMMARIZER,
        SQL_QUERY: SQL_QUERY,
        EXCEL_CREATE: EXCEL_CREATE,
        CHART_CREATE: CHART_CREATE,
        FAILURE: SELF_KNOWLEDGE,
    },
)

graph_builder.add_conditional_edges(
    DOCUMENT_SUMMARIZER,
    summary_router,
    {
        ANSWER: END,
        GENERATE: GENERATE,
        FAILURE: SELF_KNOWLEDGE,
    },
)

graph_builder.add_conditional_edges(
    GLOBAL_SUMMARIZER,
    summary_router,
    {
        ANSWER: END,
        GENERATE: GENERATE,
        FAILURE: SELF_KNOWLEDGE,
    },
)

# Web search loops back to GENERATE
graph_builder.add_edge(WEB_SEARCH, GENERATE)

# SQL query loops back to GENERATE (so LLM can interpret the result)
graph_builder.add_edge(SQL_QUERY, GENERATE)

# Excel skill terminates — the generated file IS the answer
graph_builder.add_edge(EXCEL_CREATE, END)

# Chart skill terminates — the generated chart artifact IS the answer
graph_builder.add_edge(CHART_CREATE, END)

graph_builder.add_edge(SELF_KNOWLEDGE, END)

# Compile the agent
Agent = graph_builder.compile()
