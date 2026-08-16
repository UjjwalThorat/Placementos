"""Knowledge Agent — RAG over the placement policy + FAQ.
Uses TF-IDF instead of FAISS for zero-hassle install; fine for small corpora."""
import os, re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .runner import client, MODEL

POLICY = os.path.join(os.path.dirname(__file__), "..", "data", "policy.md")

_vectorizer = None
_matrix = None
_chunks = None

def _chunk(text: str, size: int = 600) -> list:
    """Split by headings first, then by size."""
    parts = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)
    out = []
    for p in parts:
        p = p.strip()
        if not p: continue
        if len(p) <= size:
            out.append(p)
        else:
            for i in range(0, len(p), size):
                out.append(p[i:i+size])
    return out

def _index():
    global _vectorizer, _matrix, _chunks
    if _matrix is not None: return
    with open(POLICY, encoding="utf-8") as f:
        text = f.read()
    _chunks = _chunk(text)
    _vectorizer = TfidfVectorizer(stop_words="english")
    _matrix = _vectorizer.fit_transform(_chunks)

def retrieve(query: str, k: int = 3) -> list:
    _index()
    q_vec = _vectorizer.transform([query])
    sims = cosine_similarity(q_vec, _matrix)[0]
    top = sims.argsort()[::-1][:k]
    return [{"chunk": _chunks[i], "score": float(sims[i])} for i in top]

SYSTEM = """You are the Knowledge Agent for PlacementOS.
You answer student questions about placement policy strictly from the
provided context excerpts. If the answer isn't in the excerpts, say so.

Format:
ANSWER: <2-4 sentence direct answer>
SOURCE: <quote a short phrase from the excerpt(s) you used>"""

def run(question: str) -> dict:
    hits = retrieve(question, k=3)
    context = "\n\n---\n\n".join(h["chunk"] for h in hits)
    resp = client().messages.create(
        model=MODEL, max_tokens=600, system=SYSTEM,
        messages=[{"role":"user",
                   "content": f"QUESTION: {question}\n\nCONTEXT EXCERPTS:\n{context}"}],
    )
    text = "\n".join(b.text for b in resp.content if b.type == "text")
    return {"answer": text,
            "trace": [{"tool":"retrieve","input":{"q":question},
                       "output":{"chunks_returned": len(hits),
                                 "top_score": round(hits[0]["score"],3)}}]}
