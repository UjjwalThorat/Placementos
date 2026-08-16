"""Company Matching Agent — calls Eligibility Agent for every company, ranks passers.
This is the big 'agents-calling-agents' moment for the demo."""
import re
from . import db, eligibility

def _extract_score(text: str) -> int:
    m = re.search(r"FIT_SCORE:\s*(\d+)", text)
    return int(m.group(1)) if m else 0

def _extract_verdict(text: str) -> str:
    m = re.search(r"VERDICT:\s*([A-Z ]+)", text)
    return m.group(1).strip() if m else "UNKNOWN"

def run(student_id: str, top_k: int = 5) -> dict:
    """For each company, invoke the Eligibility Agent, then rank the eligible ones."""
    trace = []
    scored = []
    for comp in db.list_companies():
        result = eligibility.run(student_id, comp)
        answer = result["answer"]
        verdict = _extract_verdict(answer)
        score = _extract_score(answer)
        c = db.get_company(comp)
        scored.append({
            "company": comp, "role": c["role"], "ctc_lpa": c["ctc_lpa"],
            "sector": c["sector"], "verdict": verdict, "fit_score": score,
            "reasoning": answer,
        })
        trace.append({"tool": "eligibility_agent", "input": {"company": comp},
                      "output": {"verdict": verdict, "fit_score": score}})
    eligible = [s for s in scored if "NOT" not in s["verdict"]]
    eligible.sort(key=lambda x: (x["fit_score"], x["ctc_lpa"]), reverse=True)
    return {"recommendations": eligible[:top_k], "all_evaluated": scored,
            "trace": trace}
