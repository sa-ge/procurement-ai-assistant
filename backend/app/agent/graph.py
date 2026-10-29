"""LangGraph procurement agent.

    START -> plan --(query)--> execute --> plan ...   (loop, max N queries)
               \\--(answer / respond)--> answer -> END

* plan:    LLM sees schema + conversation + previous steps and either emits the next
           aggregation pipeline, decides it can answer, or replies directly.
* execute: validates the pipeline (read-only guard) and runs it. Errors are recorded
           in the step so the planner can self-correct on the next turn of the loop.
* answer:  LLM turns the collected results into a natural-language answer + chart spec.

Conversation memory is kept per `thread_id` by the LangGraph checkpointer, so
follow-up questions ("and in 2015?") work.
"""
import json
from datetime import datetime
from typing import Annotated, Any, Literal, Optional, TypedDict

from bson import ObjectId
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langchain_core.rate_limiters import InMemoryRateLimiter
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from app.agent import prompts
from app.agent.safety import parse_pipeline
from app.config import settings
from app.db import get_collection
from app.schema import schema_prompt

MAX_STEPS = 4
HISTORY_TURNS = 6
RESULT_CHARS_FOR_LLM = 12_000


# ---------- structured LLM outputs ----------

class Plan(BaseModel):
    action: Literal["query", "answer", "respond"] = Field(description="Next action to take.")
    reasoning: str = Field(description="One or two sentences: what you need and why.")
    pipeline: str = Field(default="", description='Aggregation pipeline as a JSON array string when action="query", else "".')
    message: str = Field(default="", description='Reply to the user when action="respond", else "".')


class Chart(BaseModel):
    type: Literal["bar", "line", "pie"]
    x_key: str = Field(description="Result field used for labels / x axis.")
    y_key: str = Field(description="Numeric result field used for values.")
    title: str


class FinalAnswer(BaseModel):
    answer: str = Field(description="Markdown answer for the user.")
    chart: Optional[Chart] = Field(default=None, description="Chart suggestion, or null.")
    chart_step: int = Field(default=-1, description="Index of the step whose rows the chart uses (-1 = last successful).")


# ---------- state ----------

class Step(TypedDict, total=False):
    reasoning: str
    pipeline: Any
    rows: list
    row_count: int
    error: str
    duration_ms: int


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    question: str
    steps: list[Step]
    plan: dict
    result: dict


# ---------- helpers ----------

def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, float):
        return round(value, 4)
    return value


def render_steps(steps: list[Step]) -> str:
    if not steps:
        return "(none yet)"
    out = []
    for i, step in enumerate(steps):
        out.append(f"Step {i}: {step.get('reasoning', '')}\nPipeline: {json.dumps(step.get('pipeline'), default=str)}")
        if step.get("error"):
            out.append(f"ERROR: {step['error']}")
        else:
            rows = json.dumps(step.get("rows", []), default=str)
            if len(rows) > RESULT_CHARS_FOR_LLM:
                rows = rows[:RESULT_CHARS_FOR_LLM] + " ...(truncated)"
            out.append(f"Result ({step.get('row_count', 0)} rows): {rows}")
    return "\n\n".join(out)


def render_history(messages: list[AnyMessage]) -> str:
    recent = messages[-(HISTORY_TURNS * 2 + 1):-1]  # exclude the current question
    if not recent:
        return "(start of conversation)"
    return "\n".join(f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}" for m in recent)


_rate_limiter = (InMemoryRateLimiter(requests_per_second=settings.llm_requests_per_minute / 60,
                                     check_every_n_seconds=0.5, max_bucket_size=1)
                 if settings.llm_requests_per_minute > 0 else None)


def get_llm():
    return init_chat_model(settings.llm_model, model_provider=settings.llm_provider,
                           temperature=settings.llm_temperature, rate_limiter=_rate_limiter)


# ---------- nodes ----------

def plan_node(state: AgentState) -> AgentState:
    steps = state.get("steps", [])
    planner = get_llm().with_structured_output(Plan)
    history = [m for m in state["messages"][-(HISTORY_TURNS * 2 + 1):-1]]
    plan: Plan = planner.invoke([
        SystemMessage(prompts.PLANNER_SYSTEM.format(schema=schema_prompt(), max_steps=MAX_STEPS)),
        *history,
        HumanMessage(prompts.PLANNER_STEPS.format(question=state["question"], steps=render_steps(steps))),
    ])
    if plan.action == "query" and len(steps) >= MAX_STEPS:
        plan.action = "answer"  # step budget exhausted: answer with what we have
    return {"plan": plan.model_dump()}


def execute_node(state: AgentState) -> AgentState:
    plan = state["plan"]
    step: Step = {"reasoning": plan["reasoning"], "pipeline": plan["pipeline"]}
    started = datetime.now()
    try:
        pipeline = parse_pipeline(plan["pipeline"])
        step["pipeline"] = jsonable(pipeline)
        rows = list(get_collection().aggregate(pipeline, maxTimeMS=settings.query_timeout_ms))
        step["rows"] = jsonable(rows)
        step["row_count"] = len(rows)
    except Exception as exc:  # noqa: BLE001 - errors are fed back to the planner
        step["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    step["duration_ms"] = int((datetime.now() - started).total_seconds() * 1000)
    return {"steps": [*state.get("steps", []), step]}


def answer_node(state: AgentState) -> AgentState:
    plan, steps = state["plan"], state.get("steps", [])
    if plan["action"] == "respond":
        result = {"answer": plan["message"], "chart": None, "chart_rows": []}
    else:
        writer = get_llm().with_structured_output(FinalAnswer)
        final: FinalAnswer = writer.invoke([
            SystemMessage(prompts.ANSWER_SYSTEM),
            HumanMessage(prompts.ANSWER_USER.format(history=render_history(state["messages"]),
                                                    question=state["question"],
                                                    steps=render_steps(steps))),
        ])
        ok_steps = [s for s in steps if not s.get("error")]
        chart_rows = []
        if final.chart and ok_steps:
            idx = final.chart_step if 0 <= final.chart_step < len(steps) and not steps[final.chart_step].get("error") else -1
            chart_rows = (steps[idx] if idx >= 0 else ok_steps[-1]).get("rows", [])
            if not chart_rows or final.chart.x_key not in chart_rows[0] or final.chart.y_key not in chart_rows[0]:
                final.chart, chart_rows = None, []
        result = {"answer": final.answer, "chart": final.chart.model_dump() if final.chart else None,
                  "chart_rows": chart_rows}
    return {"result": result, "messages": [AIMessage(result["answer"])]}


def route_after_plan(state: AgentState) -> str:
    return "execute" if state["plan"]["action"] == "query" else "answer"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("answer", answer_node)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", route_after_plan, {"execute": "execute", "answer": "answer"})
    graph.add_edge("execute", "plan")
    graph.add_edge("answer", END)
    return graph.compile(checkpointer=MemorySaver())


agent = build_graph()


def ask(question: str, thread_id: str) -> dict:
    """Run one conversational turn and return answer + full reasoning trace."""
    state = agent.invoke(
        {"messages": [HumanMessage(question)], "question": question, "steps": [], "plan": {}, "result": {}},
        config={"configurable": {"thread_id": thread_id}, "recursion_limit": 2 * MAX_STEPS + 6},
    )
    return {**state["result"], "steps": state["steps"]}
