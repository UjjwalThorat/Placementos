# PlacementOS — 7-agent placement assistant, with login

A prototype demonstrating multi-agent architecture for IIM Trichy campus
placements — now gated behind a real login, so every student gets their own
private dashboard instead of one shared page.

## Setup (5 minutes)

```bash
pip install -r requirements.txt
python data/seed.py            # (re)builds placementos.db with demo logins
streamlit run app.py
```

Then in the sidebar (after logging in as a student), paste your **Groq API
key** (get one free at console.groq.com — the demo uses <$1 of Llama 3.3
credit). Note: the underlying agent runner talks to Groq's API, not
Anthropic's — despite the earlier version of this README saying "Anthropic
API key." An Anthropic key pasted into the old field would not actually
have worked; `requirements.txt` was also missing the `groq` package
itself, which has been added.

## What's new: authentication & authorization

Two separate logins, two different experiences:

| Role | Logs in with | Can do |
|---|---|---|
| **Student** | Student ID + password | Sees **only their own** private dashboard — all 7 agents, scoped to them |
| **Admin** (Placement Committee) | Admin username + password | Add / edit / reset password / remove student records — no access to any student's agent dashboard |

**Demo credentials** (seeded by `data/seed.py`):
- Admin → username `admin`, password `admin123`
- Students → username = Student ID, password = Student ID (e.g. `p25375` / `p25375`)
  - Seeded students: `p25375` (Shubham Senani), `p25401` (Ananya Rao), `p25412` (Rahul Verma)

A student's default password is always their own Student ID at creation —
they're expected to change it from the "🔑 Change my password" panel in
their own sidebar after first login. Admins can also force a reset from
the **Edit / Remove / Reset Password** tab.

Passwords are never stored in plaintext — `agents/auth.py` hashes them
with salted PBKDF2-SHA256 (100,000 iterations) before they touch the
database.

If you run this against your **old** `placementos.db` (from before this
update), nothing is lost: `db.ensure_auth_schema()` runs on every app
start and automatically adds the `users` table plus a login for any
student who doesn't have one yet (default password = their Student ID).

## What's inside

**7 agents** (all in `agents/`), unchanged from the original prototype:
- `profile.py` — Student Profile Agent
- `eligibility.py` — Eligibility Agent (calls Profile internally)
- `matching.py` — Company Matching Agent (calls Eligibility ×10)
- `resume.py` — Resume Review Agent (ATS scoring)
- `knowledge.py` — Knowledge Agent (TF-IDF RAG over `data/policy.md`)
- `calendar_agent.py` — Calendar Agent
- `notification.py` — Notification Agent
- `router.py` — Orchestrator that dispatches chat messages

**Auth & data**:
- `auth.py` — password hashing/verification (stdlib only, no new dependency)
- `db.py` — SQLite helpers: student CRUD, user/login management, companies, deadlines
- `runner.py` — the generic agent loop (system prompt + tools + `while tool_use` loop)
- `data/seed.py` — builds SQLite with 3 students, 10 companies, 5 deadlines, and their logins
- `data/policy.md` — synthetic placement policy for the Knowledge Agent to RAG over

## Demo flow

**As a student** (log in as `p25375` / `p25375`):
1. **Profile tab** — see only your own record, click "Ask Profile Agent to summarise."
2. **Eligibility tab** — pick McKinsey → pass/fail per criterion.
3. **Recommendations tab** — "Find companies for me" → fires 10 Eligibility Agent calls, ranked table. The multi-agent showpiece.
4. **Resume tab** — upload a PDF → ATS score + 5 fixes.
5. **Chat tab** — ask "What's the dream company rule?" → Knowledge Agent + RAG citation.
6. **Reminders tab** — "Generate reminders" → Notification Agent output.
7. Log out, log back in as `p25401` — you'll see a completely different profile and eligibility results, proving the dashboard is private per student.

**As admin** (log in as `admin` / `admin123`):
1. **All Students** — see every seeded student at a glance.
2. **Add Student** — register a new student; they can log in immediately with their Student ID as both username and default password.
3. **Edit / Remove / Reset Password** — update a record, force a password reset, or remove a student.

Every agent response still shows a "🤖 handled by [Agent Name]" badge and
an expandable trace of tool calls, so the multi-agent architecture stays
visible to your evaluators.

## Add / remove students without the UI

Edit the `students` list near the top of `data/seed.py`'s `build()`
function, then `python data/seed.py` again (this wipes and rebuilds the
whole DB — prefer the Admin dashboard for incremental changes on data you
want to keep).
