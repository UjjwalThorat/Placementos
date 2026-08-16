"""Calendar Agent — deadline queries."""
from .runner import run_agent
from . import db

TOOLS = [{
    "name":"list_deadlines",
    "description":"List placement-related deadlines within the next N days.",
    "input_schema":{"type":"object",
        "properties":{"days_ahead":{"type":"integer","description":"lookahead window, e.g. 7 for this week"}},
        "required":["days_ahead"]}
}]
IMPLS = {"list_deadlines": db.list_deadlines}

SYSTEM = """You are the Calendar Agent for PlacementOS.
Use the list_deadlines tool to fetch deadlines for the appropriate window,
then present them as a clean sorted list:
  <date> — <company> — <event>  (<notes>)

Infer the window from the question (default 14 days if unclear).
End with a one-line summary of what's most urgent."""

def run(question: str) -> dict:
    return run_agent(SYSTEM, question, TOOLS, IMPLS)

def raw(days_ahead: int = 30) -> list:
    return db.list_deadlines(days_ahead)
