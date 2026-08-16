"""Notification Agent — composes reminder messages for upcoming deadlines."""
from .runner import client, MODEL
from . import db

SYSTEM = """You are the Notification Agent for PlacementOS.
Given a list of upcoming placement deadlines, compose short, friendly
reminder messages the student would receive via email/WhatsApp.

Rules:
- One reminder per deadline.
- Format: '[<days> days] <company> — <event>. <one-sentence nudge>. Due <date>.'
- Warmer tone for far-off items; urgent tone for <=2 days.
- No greetings, no signoff — just the bullet list."""

def run(days_ahead: int = 14) -> dict:
    from datetime import date
    items = db.list_deadlines(days_ahead)
    if not items:
        return {"answer": "(no upcoming deadlines in window)", "trace": []}
    today = date.today()
    lines = []
    for d in items:
        due = date.fromisoformat(d["due_date"])
        lines.append(f"- {(due-today).days} days | {d['company']} | {d['event']} | due {d['due_date']} | notes: {d['notes']}")
    user_msg = "Compose reminders for:\n" + "\n".join(lines)
    resp = client().messages.create(
        model=MODEL, max_tokens=800, system=SYSTEM,
        messages=[{"role":"user","content":user_msg}],
    )
    text = "\n".join(b.text for b in resp.content if b.type == "text")
    return {"answer": text,
            "trace":[{"tool":"list_deadlines","input":{"days_ahead":days_ahead},
                      "output":{"count":len(items)}}]}
