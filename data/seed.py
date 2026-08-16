"""Creates placementos.db with synthetic IIM Trichy placement data,
including login credentials for the Admin and each seeded student."""
import sqlite3, os, sys, json
from datetime import date, timedelta

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(THIS_DIR, ".."))
from agents import auth  # noqa: E402

DB = os.path.join(THIS_DIR, "..", "placementos.db")

DEFAULT_ADMIN_PASSWORD = "admin123"  # demo only — change after first login

def _user_row(username, password, role, student_id=None, name=None):
    h, salt = auth.hash_password(password)
    return (username, h, salt, role, student_id, name)

def build():
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    c = con.cursor()

    c.execute("""CREATE TABLE students (
        id TEXT PRIMARY KEY, name TEXT, program TEXT, batch TEXT,
        cgpa REAL, tenth REAL, twelfth REAL, backlogs INTEGER,
        specialization TEXT, prior_experience_months INTEGER,
        skills TEXT, certifications TEXT
    )""")
    c.execute("""CREATE TABLE companies (
        name TEXT PRIMARY KEY, sector TEXT, role TEXT, ctc_lpa REAL,
        min_cgpa REAL, min_tenth REAL, min_twelfth REAL, max_backlogs INTEGER,
        allowed_programs TEXT, allowed_specializations TEXT,
        min_experience_months INTEGER, description TEXT
    )""")
    c.execute("""CREATE TABLE deadlines (
        id INTEGER PRIMARY KEY, company TEXT, event TEXT,
        due_date TEXT, notes TEXT
    )""")
    c.execute("""CREATE TABLE users (
        username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, salt TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','student')),
        student_id TEXT, name TEXT
    )""")

    # --- Seeded students (edit / add more via the Admin dashboard, or here) ---
    students = [
      ("p25375", "Shubham Senani", "PGDM", "2025-27",
       8.2, 88.0, 91.5, 0, "Marketing & Analytics", 24,
       ["Python", "SQL", "PowerBI", "Excel", "Tableau", "Digital Marketing"],
       ["Google Digital Marketing", "AWS Cloud Practitioner"]),
      ("p25401", "Ananya Rao", "PGDM", "2025-27",
       7.6, 82.0, 85.0, 0, "Finance", 6,
       ["Excel", "Financial Modeling", "Python"], ["CFA Level 1"]),
      ("p25412", "Rahul Verma", "PGDM", "2025-27",
       6.9, 75.0, 78.0, 1, "Operations", 0,
       ["SQL", "Six Sigma", "Excel"], []),
    ]
    for s in students:
        c.execute("INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8], s[9],
            json.dumps(s[10]), json.dumps(s[11])))

    # --- 10 companies with realistic-ish criteria ---
    companies = [
      ("McKinsey & Company","Consulting","Business Analyst",28.0,8.5,85,85,0,
       ["PGDM"],["Strategy","Marketing & Analytics","Finance"],0,
       "Top-tier strategy consulting. Case-heavy interview."),
      ("Boston Consulting Group","Consulting","Associate",26.0,8.3,80,80,0,
       ["PGDM"],["Strategy","Marketing & Analytics","Operations"],0,
       "Strategy consulting. Values structured thinking."),
      ("Google","Tech","Associate Product Manager",32.0,8.0,80,80,1,
       ["PGDM","MBA"],["Marketing & Analytics","Strategy","Product"],12,
       "APM role. Requires product sense + analytics."),
      ("Amazon","Tech","Senior PM",24.0,7.5,75,75,1,
       ["PGDM","MBA"],["Marketing & Analytics","Operations","Product"],18,
       "Leadership Principles interviews. 6+ rounds."),
      ("TCS","IT Services","Consultant",12.0,6.5,60,60,2,
       ["PGDM","MBA"],["Any"],0,
       "Broad hiring, gentle criteria, 24-month bond."),
      ("Deloitte USI","Consulting","Consultant",18.0,7.5,75,75,1,
       ["PGDM"],["Strategy","Finance","Marketing & Analytics","Operations"],0,
       "Big-4 consulting arm. Structured interviews."),
      ("HUL","FMCG","Management Trainee",22.0,7.8,80,80,0,
       ["PGDM"],["Marketing & Analytics","Sales","Operations"],0,
       "Marquee FMCG. Frontline sales stint in year 1."),
      ("ITC","FMCG","Assistant Manager",21.0,7.5,75,75,0,
       ["PGDM"],["Marketing & Analytics","Sales","Operations"],0,
       "Rural sales rotation. Long-term careers."),
      ("Goldman Sachs","Finance","Analyst",26.0,8.5,85,85,0,
       ["PGDM"],["Finance"],6,
       "IBD / Markets. CFA a plus."),
      ("Flipkart","Tech","Category Manager",20.0,7.5,75,75,1,
       ["PGDM","MBA"],["Marketing & Analytics","Operations"],6,
       "E-commerce category role. Data-heavy."),
    ]
    for row in companies:
        c.execute("INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (row[0],row[1],row[2],row[3],row[4],row[5],row[6],row[7],
                   json.dumps(row[8]), json.dumps(row[9]), row[10], row[11]))

    # --- Deadlines over the next 3 weeks ---
    today = date.today()
    deadlines = [
      ("McKinsey & Company","Resume Shortlist Submission", today+timedelta(days=2),
       "Upload via placement portal by 5pm."),
      ("Google","Online Assessment", today+timedelta(days=4),
       "90-min OA, product + analytics questions."),
      ("HUL","Group Discussion", today+timedelta(days=7),
       "8-person GD, dress code formal."),
      ("Deloitte USI","Pre-Placement Talk", today+timedelta(days=1),
       "Auditorium, 6pm. Attendance mandatory."),
      ("Goldman Sachs","CV Submission", today+timedelta(days=10),
       "1-page CV, IIM Trichy format."),
    ]
    for i,(comp,evt,d,notes) in enumerate(deadlines,1):
        c.execute("INSERT INTO deadlines VALUES (?,?,?,?,?)",
                  (i,comp,evt,d.isoformat(),notes))

    # --- Logins: 1 admin + 1 per seeded student (default password = Student ID) ---
    users = [_user_row("admin", DEFAULT_ADMIN_PASSWORD, "admin",
                        name="Placement Committee Admin")]
    for s in students:
        users.append(_user_row(s[0], s[0], "student", student_id=s[0], name=s[1]))
    c.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", users)

    con.commit(); con.close()
    print(f"Seeded {DB}")
    print(f"  Admin login   -> username: admin      password: {DEFAULT_ADMIN_PASSWORD}")
    for s in students:
        print(f"  Student login -> username: {s[0]}   password: {s[0]}   ({s[1]})")

if __name__ == "__main__":
    build()
