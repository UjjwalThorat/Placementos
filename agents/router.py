"""Router / Orchestrator — classifies the user's chat message and dispatches
to the right agent(s). One tiny LLM call per user message."""
import json
from .runner import client, MODEL
from . import eligibility, matching, knowledge, calendar_agent, notification, profile

INTENTS = ["eligibility","recommendations","knowledge","calendar","notification",
           "profile","other"]

SYSTEM = f"""You are the Router for PlacementOS. Classify the user's message
into ONE of: {INTENTS}. Also extract 'company' if any company name is mentioned.

Respond ONLY as compact JSON: {{"intent":"...", "company":"...optional..."}}

Definitions:
- eligibility: "am I eligible for <company>?", "can I apply to <company>?"
- recommendations: "which companies should I apply to?", "suggest companies"
- knowledge: policy, dream company rule, offer acceptance, dress code, FAQs
- calendar: deadlines, "what's due", "upcoming events"
- notification: "send reminders", "notify me"
- profile: "my profile", "summarise me"
- other: anything else"""

def classify(message: str) -> dict:
    resp = client().messages.create(
        model=MODEL, max_tokens=150, system=SYSTEM,
        messages=[{"role":"user","content":message}])
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    try:
        start = text.find("{"); end = text.rfind("}")+1
        return json.loads(text[start:end])
    except Exception:
        return {"intent":"other"}

def dispatch(message: str, student_id: str) -> dict:
    plan = classify(message)
    intent = plan.get("intent","other")
    company = plan.get("company")

    if intent == "eligibility" and company:
        r = eligibility.run(student_id, company)
        return {"agent":"Eligibility Agent (+ Student Profile Agent)", **r}
    if intent == "recommendations":
        r = matching.run(student_id)
        summary = "**Top matches:**\n" + "\n".join(
            f"- {x['company']} ({x['role']}, ₹{x['ctc_lpa']}L) — fit {x['fit_score']}"
            for x in r["recommendations"])
        return {"agent":"Company Matching Agent → Eligibility Agent (×10)",
                "answer": summary, "trace": r["trace"], "table": r["recommendations"]}
    if intent == "knowledge":
        r = knowledge.run(message)
        return {"agent":"Knowledge Agent (RAG)", **r}
    if intent == "calendar":
        r = calendar_agent.run(message)
        return {"agent":"Calendar Agent", **r}
    if intent == "notification":
        r = notification.run()
        return {"agent":"Notification Agent", **r}
    if intent == "profile":
        r = profile.run(student_id)
        return {"agent":"Student Profile Agent", **r}

    return {"agent":"Router (no match)",
            "answer":"I can help with eligibility, recommendations, policy questions, "
                     "deadlines, reminders, or your profile. Try one of those.",
            "trace":[{"tool":"classify","input":{"message":message},"output":plan}]}
