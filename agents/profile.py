"""Student Profile Agent — extracts + summarises a student's profile."""
from .runner import run_agent
from . import db

TOOLS = [{
    "name": "get_student",
    "description": "Fetch a student's academic and professional profile by ID.",
    "input_schema": {"type":"object",
        "properties":{"student_id":{"type":"string"}},
        "required":["student_id"]}
}]
IMPLS = {"get_student": db.get_student}

SYSTEM = """You are the Student Profile Agent for PlacementOS.
Given a student_id, fetch their profile and return a crisp 4-6 line summary
covering: program, CGPA, 10th/12th, backlogs, specialization, prior experience,
top 3 skills, top 1 certification. No fluff, no markdown headers."""

def run(student_id: str) -> dict:
    return run_agent(SYSTEM, f"Summarise student {student_id}", TOOLS, IMPLS)

def raw(student_id: str) -> dict:
    """Direct fetch (no LLM) — for UI panels that just need the data."""
    return db.get_student(student_id)
