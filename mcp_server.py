#!/usr/bin/env python3
"""Optional MCP bridge: expose Laya as tools for MCP-capable code agents
(Cline, Roo Code, Claude Desktop/Code, AIOS, ...).

Install:   start.bat mcp        (installs the `mcp` package into .venv)
Run:       .venv\\Scripts\\python.exe mcp_server.py     (stdio, launched by the agent)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from mcp.server.fastmcp import FastMCP  # noqa: E402

from laya_runtime import LayaRuntime  # noqa: E402

RUNTIME = LayaRuntime()
mcp = FastMCP("laya")


@mcp.tool()
def laya_decide(state: object, questions: dict, model: str = None) -> str:
    """Answer typed questions about a state (text, email, ticket or JSON object).

    state: the content to evaluate.
    questions: object of question_id -> {type: choice|noul|score, instructions, criteria}.
      choice: criteria is {option: description}; noul: yes/no; score: criteria is [level descriptions].
    model: optional checkpoint override (english | multilingual | typed-decisions).
    Returns JSON: {model, latency_ms, answers: {question_id: answer}}.
    """
    return json.dumps(RUNTIME.predict(state, questions, model), ensure_ascii=False, indent=2)


@mcp.tool()
def laya_triage(state: object, model: str = None) -> str:
    """Customer-support triage preset: intent, urgency, frustration, refund, churn risk."""
    import laya

    return json.dumps(
        RUNTIME.predict(state, laya.triage_questions(), model), ensure_ascii=False, indent=2
    )


@mcp.tool()
def laya_guard(prompt: object, model: str = None) -> str:
    """LLM guardrail preset: jailbreak / prompt-injection / sensitive-data / harm severity."""
    import laya

    return json.dumps(
        RUNTIME.predict(prompt, laya.guard_questions(), model), ensure_ascii=False, indent=2
    )


@mcp.tool()
def laya_email(body: str, sender: str = "", subject: str = "", model: str = None) -> str:
    """Inbound-email triage preset: category, spam, phishing, urgency, needs_reply."""
    import laya

    state = {"from": sender, "subject": subject, "body": body}
    return json.dumps(
        RUNTIME.predict(state, laya.email_questions(), model), ensure_ascii=False, indent=2
    )


@mcp.tool()
def laya_health() -> str:
    """Report which Laya checkpoints are available and the active device."""
    return json.dumps(
        {"device": RUNTIME.device, "available": RUNTIME.available()}, ensure_ascii=False
    )


if __name__ == "__main__":
    mcp.run()
