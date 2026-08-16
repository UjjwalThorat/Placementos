"""Eligibility Agent — decides if a student passes a company's criteria."""
from .runner import run_agent
from . import db

TOOLS = [
  {"name":"get_student","description":"Fetch student profile by id.",
   "input_schema":{"type":"object","properties":{"student_id":{"type":"string"}},
                   "required":["student_id"]}},
  {"name":"get_company","description":"Fetch a company's eligibility criteria.",
   "input_schema":{"type":"object","properties":{"name":{"type":"string"}},
                   "required":["name"]}},
]
IMPLS = {"get_student": db.get_student, "get_company": db.get_company}

SYSTEM = """You are the Eligibility Agent for PlacementOS.
Given a student_id and company name, use the tools to fetch BOTH,
then compare each criterion (CGPA, 10th %, 12th %, backlogs, program,
specialization, prior experience months).

Return your answer in this exact format:

VERDICT: ELIGIBLE  |  NOT ELIGIBLE  |  ELIGIBLE WITH CAVEAT
FIT_SCORE: <0-100>
CRITERIA:
- CGPA: <student value> vs required <company value> → PASS/FAIL
- 10th: ...
- 12th: ...
- Backlogs: ...
- Program: ...
- Specialization: ...
- Experience: ...
ADVICE: <one line, actionable>

Be strict. 'Any' specialization means all pass."""

def run(student_id: str, company: str) -> dict:
    return run_agent(SYSTEM,
        f"Check eligibility of student {student_id} for {company}.",
        TOOLS, IMPLS)
