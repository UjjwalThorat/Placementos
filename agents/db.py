import sqlite3, os, json
from . import auth

DB = os.path.join(os.path.dirname(__file__), "..", "placementos.db")

def _conn():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

# ==================================================================
# Students
# ==================================================================

def get_student(student_id: str) -> dict:
    row = _conn().execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not row: return {"error": f"no student {student_id}"}
    d = dict(row)
    d["skills"] = json.loads(d["skills"])
    d["certifications"] = json.loads(d["certifications"])
    return d

def list_students() -> list:
    """Summary rows for the admin's 'all students' table."""
    rows = _conn().execute(
        "SELECT id, name, program, batch, specialization, cgpa, backlogs "
        "FROM students ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]

def student_exists(student_id: str) -> bool:
    return _conn().execute("SELECT 1 FROM students WHERE id=?", (student_id,)).fetchone() is not None

def create_student(student_id, name, program, batch, cgpa, tenth, twelfth, backlogs,
                    specialization, prior_experience_months, skills, certifications,
                    password=None):
    """Admin action: inserts the student record AND creates their student login.
    If `password` is omitted, the default password is the student's own ID —
    tell them to change it after first login."""
    con = _conn()
    con.execute("INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
        student_id, name, program, batch, cgpa, tenth, twelfth, backlogs,
        specialization, prior_experience_months,
        json.dumps(skills), json.dumps(certifications)))
    con.commit(); con.close()
    create_user(student_id, password or student_id, "student",
                student_id=student_id, name=name)

def update_student(student_id, **fields):
    """Admin action: partial update of a student record. Keys in `fields`
    must match column names; 'skills'/'certifications' are JSON-encoded
    automatically if present."""
    if not fields: return
    fields = dict(fields)
    if "skills" in fields: fields["skills"] = json.dumps(fields["skills"])
    if "certifications" in fields: fields["certifications"] = json.dumps(fields["certifications"])
    cols = ", ".join(f"{k}=?" for k in fields)
    con = _conn()
    con.execute(f"UPDATE students SET {cols} WHERE id=?", (*fields.values(), student_id))
    if "name" in fields:  # keep the login's display name in sync
        con.execute("UPDATE users SET name=? WHERE student_id=?", (fields["name"], student_id))
    con.commit(); con.close()

def delete_student(student_id: str):
    """Admin action: removes the student record AND their login."""
    con = _conn()
    con.execute("DELETE FROM students WHERE id=?", (student_id,))
    con.execute("DELETE FROM users WHERE student_id=?", (student_id,))
    con.commit(); con.close()

# ==================================================================
# Companies / Deadlines (unchanged)
# ==================================================================

def get_company(name: str) -> dict:
    row = _conn().execute("SELECT * FROM companies WHERE name=?", (name,)).fetchone()
    if not row: return {"error": f"no company {name}"}
    d = dict(row)
    d["allowed_programs"] = json.loads(d["allowed_programs"])
    d["allowed_specializations"] = json.loads(d["allowed_specializations"])
    return d

def list_companies() -> list:
    rows = _conn().execute("SELECT name FROM companies ORDER BY ctc_lpa DESC").fetchall()
    return [r["name"] for r in rows]

def list_deadlines(days_ahead: int = 30) -> list:
    from datetime import date, timedelta

    cutoff = (date.today() + timedelta(days=days_ahead)).isoformat()
    today = date.today().isoformat()

    rows = _conn().execute(
        "SELECT * FROM deadlines WHERE due_date>=? AND due_date<=? ORDER BY due_date",
        (today, cutoff)
    ).fetchall()

    return [dict(r) for r in rows]


def create_deadline(company, event, due_date, notes=""):
    con = _conn()

    con.execute(
        "INSERT INTO deadlines (company, event, due_date, notes) VALUES (?, ?, ?, ?)",
        (company, event, due_date, notes)
    )

    con.commit()
    con.close()


def update_deadline(deadline_id, company, event, due_date, notes=""):
    con = _conn()

    con.execute(
        """UPDATE deadlines
           SET company=?, event=?, due_date=?, notes=?
           WHERE id=?""",
        (company, event, due_date, notes, deadline_id)
    )

    con.commit()
    con.close()


def delete_deadline(deadline_id):
    con = _conn()

    con.execute(
        "DELETE FROM deadlines WHERE id=?",
        (deadline_id,)
    )

    con.commit()
    con.close()


def list_all_deadlines():
    rows = _conn().execute(
        "SELECT * FROM deadlines ORDER BY due_date"
    ).fetchall()

    return [dict(r) for r in rows]


def update_deadline(deadline_id, due_date, company, event, notes=""):
    con = _conn()
    con.execute(
        """UPDATE deadlines
           SET due_date=?, company=?, event=?, notes=?
           WHERE id=?""",
        (due_date, company, event, notes, deadline_id)
    )
    con.commit()
    con.close()


def delete_deadline(deadline_id):
    con = _conn()
    con.execute(
        "DELETE FROM deadlines WHERE id=?",
        (deadline_id,)
    )
    con.commit()
    con.close()


def list_all_deadlines():
    rows = _conn().execute(
        "SELECT * FROM deadlines ORDER BY due_date"
    ).fetchall()
    return [dict(r) for r in rows]
# ==================================================================
# Auth / Users
# ==================================================================

def ensure_auth_schema():
    """Idempotent migration: adds the `users` table if it's missing and
    seeds a default admin + a login for any student that doesn't have one
    yet. Safe to call on every app start, including against an existing
    (pre-auth) placementos.db."""
    con = _conn()
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','student')),
        student_id TEXT,
        name TEXT
    )""")
    con.commit()
    has_admin = con.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone()
    covered = {r["student_id"] for r in
               con.execute("SELECT student_id FROM users WHERE role='student'").fetchall()}
    all_students = con.execute("SELECT id, name FROM students").fetchall()
    con.close()

    if not has_admin:
        create_user("admin", "admin123", "admin", name="Placement Committee Admin")
    for s in all_students:
        if s["id"] not in covered:
            create_user(s["id"], s["id"], "student", student_id=s["id"], name=s["name"])

def create_user(username, password, role, student_id=None, name=None):
    h, salt = auth.hash_password(password)
    con = _conn()
    con.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?)",
                (username, h, salt, role, student_id, name))
    con.commit(); con.close()

def verify_login(username: str, password: str):
    """Returns {role, student_id, name, username} on success, else None."""
    row = _conn().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row: return None
    if not auth.verify_password(password, row["password_hash"], row["salt"]): return None
    return {"role": row["role"], "student_id": row["student_id"],
            "name": row["name"], "username": row["username"]}

def reset_password(username: str, new_password: str):
    h, salt = auth.hash_password(new_password)
    con = _conn()
    con.execute("UPDATE users SET password_hash=?, salt=? WHERE username=?",
                (h, salt, username))
    con.commit(); con.close()

def username_exists(username: str) -> bool:
    return _conn().execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone() is not None
