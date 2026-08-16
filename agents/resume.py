"""Resume Review Agent — ATS score + concrete improvement suggestions."""
from .runner import client, MODEL

SYSTEM = """You are the Resume Review Agent for PlacementOS, specialised for
MBA/PGDM campus placements at Indian B-schools.

Given the raw text of a resume, produce:

ATS_SCORE: <0-100>  (harsh; deduct for weak verbs, missing metrics, poor formatting cues)
ONE_LINE_VERDICT: <10 words max>

TOP 5 IMPROVEMENTS (each a single actionable sentence, most impactful first):
1.
2.
3.
4.
5.

KEYWORDS_MISSING: <comma-separated list of 5-10 role-relevant keywords the resume lacks,
tuned for consulting / product / marketing analyst roles>

STRENGTHS: <2 bullets, one line each>

Be specific — reference actual lines / phrases from the resume."""

def run(resume_text: str, target_role: str = "consulting / product management") -> dict:
    if not resume_text.strip():
        return {"answer": "(empty resume)", "trace": []}
    resp = client().messages.create(
        model=MODEL, max_tokens=1500, system=SYSTEM,
        messages=[{"role":"user",
                   "content": f"Target roles: {target_role}\n\nRESUME:\n{resume_text[:6000]}"}],
    )
    text = "\n".join(b.text for b in resp.content if b.type == "text")
    return {"answer": text, "trace": [{"tool":"llm_review","input":{"chars":len(resume_text)},
                                       "output":"scored"}]}
