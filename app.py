"""PlacementOS — 7-agent Streamlit prototype, now with role-based login.

Two roles:
  - Student : logs in with Student ID + password -> lands on their OWN
              private dashboard (the 7 agents, scoped only to them).
  - Admin   : Placement Committee login -> manages student records
              (add / edit / reset password / remove). No access to any
              individual student's agent dashboard.
"""
import os, sys, io
import streamlit as st

# Ensure DB exists
if not os.path.exists("placementos.db"):
    sys.path.insert(0, os.path.dirname(__file__))
    from data.seed import build; build()

from agents import profile, eligibility, matching, resume, knowledge, calendar_agent, notification, router, db

# Idempotent: adds the users table + default logins if this is an older DB
db.ensure_auth_schema()

st.set_page_config(page_title="PlacementOS", page_icon="🎓", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = None  # {"role","student_id","name","username"} once logged in

def _require_key():
    if not (os.environ.get("GROQ_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        st.warning("Paste your API key in the sidebar to continue.")
        st.stop()

def agent_badge(name: str):
    st.markdown(
        f"<div style='display:inline-block;padding:4px 10px;background:#eef;"
        f"border-radius:12px;font-size:12px;color:#224;margin-bottom:8px;'>"
        f"🤖 handled by <b>{name}</b></div>", unsafe_allow_html=True)

def trace_expander(trace):
    if not trace: return
    with st.expander(f"🔍 Agent trace ({len(trace)} tool call(s))"):
        for i,t in enumerate(trace,1):
            st.markdown(f"**{i}. {t['tool']}**")
            st.json({"input":t.get("input"),"output":t.get("output")})

def logout_button():
    if st.sidebar.button("🚪 Log out", use_container_width=True):
        st.session_state.auth = None
        st.rerun()

# =====================================================================
# LOGIN PAGE
# =====================================================================
def render_login():
    st.title("🎓 PlacementOS")
    st.caption("7-agent placement assistant · IIM Trichy — sign in to continue")

    tab_student, tab_admin = st.tabs(["🧑‍🎓 Student Login", "🛠️ Admin Login"])

    with tab_student:
        with st.form("student_login_form"):
            sid = st.text_input("Student ID", placeholder="e.g. p25375")
            pwd = st.text_input("Password", type="password")
            go = st.form_submit_button("Log in", use_container_width=True)
        if go:
            user = db.verify_login(sid.strip(), pwd)
            if user and user["role"] == "student":
                st.session_state.auth = user
                st.rerun()
            else:
                st.error("Invalid Student ID or password.")
        st.caption("First time logging in? Your default password is your Student ID — "
                   "you can change it from your dashboard afterwards. "
                   "Don't have a login? Ask the Placement Committee to add you.")

    with tab_admin:
        with st.form("admin_login_form"):
            uname = st.text_input("Admin username", placeholder="admin")
            pwd2 = st.text_input("Password", type="password", key="admin_pwd_field")
            go2 = st.form_submit_button("Log in", use_container_width=True)
        if go2:
            user = db.verify_login(uname.strip(), pwd2)
            if user and user["role"] == "admin":
                st.session_state.auth = user
                st.rerun()
            else:
                st.error("Invalid admin username or password.")

# =====================================================================
# ADMIN DASHBOARD — manage student records
# =====================================================================
def render_admin_dashboard():
    auth = st.session_state.auth
    with st.sidebar:
        st.title("🎓 PlacementOS")
        st.caption(f"Signed in as **{auth['name'] or auth['username']}** · Admin")
        st.divider()
        logout_button()

    st.header("🛠️ Placement Committee — Admin Dashboard")
    st.caption("Admins manage student records here and have no access to any "
               "individual student's private agent dashboard.")

    tab_list, tab_add, tab_edit,tab_deadlines = st.tabs(
        ["📋 All Students", "➕ Add Student", "✏️ Edit / Remove / Reset Password",
        "📅 Manage Deadlines"])

    # ---------------- All students ----------------
    with tab_list:
        rows = db.list_students()
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(f"{len(rows)} student(s) on file.")

    # ---------------- Add student ----------------
    with tab_add:
        st.subheader("Add a new student")
        with st.form("add_student_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            sid = c1.text_input("Student ID*", placeholder="p25xxx")
            name = c2.text_input("Full name*")
            program = c1.text_input("Program", "PGDM")
            batch = c2.text_input("Batch", "2025-27")
            specialization = c1.text_input("Specialization", "Marketing & Analytics")
            prior_exp = c2.number_input("Prior experience (months)", 0, 240, 0)
            cgpa = c1.number_input("CGPA", 0.0, 10.0, 7.5, step=0.1)
            tenth = c2.number_input("10th %", 0.0, 100.0, 80.0)
            twelfth = c1.number_input("12th %", 0.0, 100.0, 80.0)
            backlogs = c2.number_input("Backlogs", 0, 20, 0)
            skills = st.text_input("Skills (comma-separated)", "Excel, Python")
            certs = st.text_input("Certifications (comma-separated)", "")
            password = st.text_input(
                "Initial password (leave blank to default to the Student ID)",
                type="password")
            submitted = st.form_submit_button("Add student", use_container_width=True)
        if submitted:
            sid_clean = sid.strip()
            if not sid_clean or not name.strip():
                st.error("Student ID and name are required.")
            elif db.student_exists(sid_clean):
                st.error(f"Student ID {sid_clean} already exists.")
            else:
                db.create_student(
                    sid_clean, name.strip(), program, batch, cgpa, tenth, twelfth,
                    int(backlogs), specialization, int(prior_exp),
                    [s.strip() for s in skills.split(",") if s.strip()],
                    [c.strip() for c in certs.split(",") if c.strip()],
                    password=password or None)
                shown_pw = password or sid_clean
                st.success(f"Added **{name}** ({sid_clean}). "
                           f"Login password: `{shown_pw}` — share this with the student.")

    # ---------------- Edit / remove / reset password ----------------
    with tab_edit:
        rows = db.list_students()
        ids = [r["id"] for r in rows]
        if not ids:
            st.info("No students yet — add one first.")
        else:
            sel = st.selectbox("Select student", ids)
            cur = db.get_student(sel)

            with st.form("edit_student_form"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Full name", cur["name"])
                program = c2.text_input("Program", cur["program"])
                batch = c1.text_input("Batch", cur["batch"])
                specialization = c2.text_input("Specialization", cur["specialization"])
                prior_exp = c1.number_input("Prior experience (months)", 0, 240,
                                             int(cur["prior_experience_months"]))
                cgpa = c2.number_input("CGPA", 0.0, 10.0, float(cur["cgpa"]), step=0.1)
                tenth = c1.number_input("10th %", 0.0, 100.0, float(cur["tenth"]))
                twelfth = c2.number_input("12th %", 0.0, 100.0, float(cur["twelfth"]))
                backlogs = c1.number_input("Backlogs", 0, 20, int(cur["backlogs"]))
                skills = st.text_input("Skills (comma-separated)", ", ".join(cur["skills"]))
                certs = st.text_input("Certifications (comma-separated)",
                                       ", ".join(cur["certifications"]))
                save = st.form_submit_button("Save changes", use_container_width=True)
            if save:
                db.update_student(sel, name=name, program=program, batch=batch,
                                   specialization=specialization,
                                   prior_experience_months=int(prior_exp),
                                   cgpa=cgpa, tenth=tenth, twelfth=twelfth,
                                   backlogs=int(backlogs),
                                   skills=[s.strip() for s in skills.split(",") if s.strip()],
                                   certifications=[c.strip() for c in certs.split(",") if c.strip()])
                st.success("Student record updated.")
                st.rerun()

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Reset password**")
                new_pwd = st.text_input("New password", type="password", key="reset_pwd_field")
                if st.button("Reset password", use_container_width=True):
                    if new_pwd:
                        db.reset_password(sel, new_pwd)
                        st.success(f"Password reset for {sel}.")
                    else:
                        st.warning("Enter a new password first.")
            with c2:
                st.markdown("**Remove student**")
                confirm = st.checkbox(f"I confirm I want to delete {sel}")
                if st.button("🗑️ Delete student", use_container_width=True, disabled=not confirm):
                    db.delete_student(sel)
                    st.success(f"Deleted {sel}.")
                    st.rerun()
    # ---------------- Manage deadlines ----------------
    with tab_deadlines:
        st.subheader("📅 Manage Placement Deadlines")
        st.caption(
            "Add, edit, or remove placement deadlines. "
            "Changes are immediately reflected in student dashboards."
        )

        # ==================== VIEW ====================
        deadlines = db.list_all_deadlines()

        if deadlines:
            st.dataframe(
                deadlines,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No deadlines currently exist.")

        st.divider()

        # ==================== ADD ====================
        st.subheader("➕ Add Deadline")

        companies = db.list_companies()

        with st.form("add_deadline_form", clear_on_submit=True):
            c1, c2 = st.columns(2)

            company = c1.selectbox(
                "Company",
                companies
            )

            event = c2.text_input(
                "Event",
                placeholder="Online Assessment / Interview / PPT"
            )

            due_date = c1.date_input("Due date")

            notes = c2.text_input(
                "Notes",
                placeholder="Additional information"
            )

            add_deadline = st.form_submit_button(
                "Add Deadline",
                use_container_width=True
            )

        if add_deadline:
            if not event.strip():
                st.error("Event is required.")
            else:
                db.create_deadline(
                    company=company,
                    event=event.strip(),
                    due_date=due_date.isoformat(),
                    notes=notes.strip()
                )

                st.success(
                    f"Deadline added for {company} on {due_date}."
                )
                st.rerun()

        st.divider()

        # ==================== EDIT / DELETE ====================
        st.subheader("✏️ Edit / Delete Deadline")

        deadlines = db.list_all_deadlines()

        if deadlines:
            deadline_options = {
                f"{d['due_date']} — {d['company']} — {d['event']}": d
                for d in deadlines
            }

            selected_label = st.selectbox(
                "Select deadline",
                list(deadline_options.keys())
            )

            selected = deadline_options[selected_label]

            company_index = (
                companies.index(selected["company"])
                if selected["company"] in companies
                else 0
            )

            from datetime import date

            with st.form("edit_deadline_form"):
                c1, c2 = st.columns(2)

                edit_company = c1.selectbox(
                    "Company",
                    companies,
                    index=company_index
                )

                edit_event = c2.text_input(
                    "Event",
                    value=selected["event"]
                )

                edit_date = c1.date_input(
                    "Due date",
                    value=date.fromisoformat(selected["due_date"])
                )

                edit_notes = c2.text_input(
                    "Notes",
                    value=selected["notes"] or ""
                )

                save_deadline = st.form_submit_button(
                    "💾 Save Changes",
                    use_container_width=True
                )

            if save_deadline:
                if not edit_event.strip():
                    st.error("Event is required.")
                else:
                    db.update_deadline(
                        deadline_id=selected["id"],
                        company=edit_company,
                        event=edit_event.strip(),
                        due_date=edit_date.isoformat(),
                        notes=edit_notes.strip()
                    )

                    st.success("Deadline updated successfully.")
                    st.rerun()

            st.divider()

            confirm_delete = st.checkbox(
                f"I confirm I want to delete "
                f"**{selected['company']} — {selected['event']}**"
            )

            if st.button(
                "🗑️ Delete Deadline",
                disabled=not confirm_delete,
                use_container_width=True
            ):
                db.delete_deadline(selected["id"])
                st.success("Deadline deleted successfully.")
                st.rerun()
# =====================================================================
# STUDENT DASHBOARD — private, scoped to the logged-in student only
# =====================================================================
def render_student_dashboard():
    auth = st.session_state.auth
    student_id = auth["student_id"]

    with st.sidebar:
        st.title("🎓 PlacementOS")
        st.caption(f"Signed in as **{auth['name'] or student_id}** ({student_id})")
        key = st.text_input("Groq API key", type="password",
                            value=os.environ.get("GROQ_API_KEY",""),
                            help="Get one at console.groq.com. Only used in this session.")
        if key:
            os.environ["GROQ_API_KEY"] = key
        st.divider()
        st.subheader("The 7 agents")
        for name in ["Student Profile","Eligibility","Resume Review",
                     "Company Matching","Knowledge (RAG)","Calendar","Notification"]:
            st.markdown(f"- 🤖 **{name} Agent**")
        st.divider()
        with st.expander("🔑 Change my password"):
            old_pw = st.text_input("Current password", type="password", key="old_pw")
            new_pw = st.text_input("New password", type="password", key="new_pw")
            if st.button("Update password"):
                if db.verify_login(auth["username"], old_pw) is None:
                    st.error("Current password is incorrect.")
                elif not new_pw:
                    st.warning("Enter a new password.")
                else:
                    db.reset_password(auth["username"], new_pw)
                    st.success("Password updated.")
        logout_button()

    # --- Tabs (same 7-agent experience as before, now private to this student) ---
    tab_profile, tab_elig, tab_reco, tab_resume, tab_cal, tab_notif, tab_chat = st.tabs(
        ["👤 Profile","✅ Eligibility","🎯 Recommendations","📄 Resume Review",
         "📅 Deadlines","🔔 Reminders","💬 Chat"])

    # ------------- PROFILE TAB -------------
    with tab_profile:
        st.header("Your profile")
        st.caption("Fetched by the Student Profile Agent (or shown raw from DB).")
        p = profile.raw(student_id)
        if "error" in p:
            st.error(p["error"])
        else:
            agent_badge("Student Profile Agent")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("CGPA", p["cgpa"])
            c2.metric("10th %", p["tenth"])
            c3.metric("12th %", p["twelfth"])
            c4.metric("Backlogs", p["backlogs"])
            st.write(f"**{p['name']}** · {p['program']} {p['batch']} · "
                     f"{p['specialization']} · {p['prior_experience_months']} months prior exp")
            st.write("**Skills:** " + ", ".join(p["skills"]))
            st.write("**Certifications:** " + ", ".join(p["certifications"]))
            if st.button("Ask the Profile Agent to summarise me"):
                _require_key()
                with st.spinner("Profile Agent thinking..."):
                    r = profile.run(student_id)
                st.info(r["answer"])
                trace_expander(r["trace"])

    # ------------- ELIGIBILITY TAB -------------
    with tab_elig:
        st.header("Company eligibility check")
        st.caption("Eligibility Agent calls the Student Profile Agent internally.")
        comp = st.selectbox("Company", db.list_companies())

        if st.button("Check eligibility"):
            _require_key()

            try:
                with st.spinner("Eligibility Agent thinking..."):
                    r = eligibility.run(student_id, comp)

                agent_badge("Eligibility Agent → Student Profile Agent")
                st.text(r["answer"])
                trace_expander(r["trace"])

            except Exception as e:
                st.error(f"Eligibility check failed: {e}")
    # ------------- RECOMMENDATIONS TAB -------------
    with tab_reco:
        st.header("Personalised company recommendations")
        st.caption("Company Matching Agent invokes Eligibility Agent for every company, "
                   "then ranks the eligible ones. The multi-agent showpiece.")
        if st.button("Find companies for me"):
            _require_key()
            with st.spinner("Evaluating 10 companies (this fires 10 agent calls)…"):
                r = matching.run(student_id, top_k=5)
            agent_badge(f"Company Matching Agent → Eligibility Agent ×{len(r['all_evaluated'])}")
            st.subheader("Top matches")
            st.dataframe(
                [{"Company":x["company"],"Role":x["role"],"CTC (₹L)":x["ctc_lpa"],
                  "Sector":x["sector"],"Fit":x["fit_score"],"Verdict":x["verdict"]}
                 for x in r["recommendations"]],
                use_container_width=True, hide_index=True)
            with st.expander("See reasoning for each top match"):
                for x in r["recommendations"]:
                    st.markdown(f"### {x['company']}")
                    st.text(x["reasoning"])
            with st.expander("See all 10 evaluations"):
                st.dataframe(
                    [{"Company":x["company"],"Verdict":x["verdict"],"Fit":x["fit_score"]}
                     for x in r["all_evaluated"]],
                    use_container_width=True, hide_index=True)
            trace_expander(r["trace"])

    # ------------- RESUME TAB -------------
    with tab_resume:
        st.header("Resume review")
        st.caption("Resume Review Agent — ATS score, top-5 fixes, missing keywords.")
        target = st.text_input("Target role(s)", "consulting / product management")
        up = st.file_uploader("Upload resume (PDF or text)", type=["pdf","txt"])
        pasted = st.text_area("...or paste resume text", height=180)
        if st.button("Review resume"):
            _require_key()
            text = ""
            if up:
                if up.name.endswith(".pdf"):
                    from pypdf import PdfReader
                    reader = PdfReader(io.BytesIO(up.read()))
                    text = "\n".join((p.extract_text() or "") for p in reader.pages)
                else:
                    text = up.read().decode("utf-8", errors="ignore")
            text = text or pasted
            if not text.strip():
                st.warning("Upload or paste a resume first.")
            else:
                with st.spinner("Resume Agent scoring…"):
                    r = resume.run(text, target_role=target)
                agent_badge("Resume Review Agent")
                st.text(r["answer"])
                trace_expander(r["trace"])

    # ------------- CALENDAR TAB -------------
    with tab_cal:
        st.header("Upcoming deadlines")
        st.caption("Data from the Calendar Agent's underlying store.")
        agent_badge("Calendar Agent")
        ds = calendar_agent.raw(30)
        st.dataframe(
            [{"Date":d["due_date"],"Company":d["company"],"Event":d["event"],"Notes":d["notes"]} for d in ds],
            use_container_width=True, hide_index=True)
        q = st.text_input("Ask the Calendar Agent",
                          "What deadlines do I have this week?")
        if st.button("Ask"):
            _require_key()
            with st.spinner("Calendar Agent thinking…"):
                r = calendar_agent.run(q)
            st.info(r["answer"])
            trace_expander(r["trace"])

    # ------------- NOTIFICATION TAB -------------
    with tab_notif:
        st.header("Reminders")
        st.caption("Notification Agent composes messages the student would receive.")
        window = st.slider("Look ahead (days)", 3, 30, 14)
        if st.button("Generate today's reminders"):
            _require_key()
            with st.spinner("Notification Agent drafting…"):
                r = notification.run(window)
            agent_badge("Notification Agent")
            st.text(r["answer"])
            trace_expander(r["trace"])

    # ------------- CHAT TAB -------------
    with tab_chat:
        st.header("Chat")
        st.caption("Router classifies your question and dispatches to the right agent.")
        chat_key = f"chat_{student_id}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []
        for msg in st.session_state[chat_key]:
            with st.chat_message(msg["role"]):
                if msg.get("agent"):
                    agent_badge(msg["agent"])
                st.markdown(msg["content"])
        prompt = st.chat_input("Ask about eligibility, companies, policy, deadlines…")
        if prompt:
            _require_key()
            st.session_state[chat_key].append({"role":"user","content":prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Router → agent…"):
                    r = router.dispatch(prompt, student_id)
                agent_badge(r["agent"])
                st.markdown(r.get("answer","(no answer)"))
                if r.get("table"):
                    st.dataframe(
                        [{"Company":x["company"],"Role":x["role"],"CTC":x["ctc_lpa"],
                          "Fit":x["fit_score"]} for x in r["table"]],
                        use_container_width=True, hide_index=True)
                trace_expander(r.get("trace",[]))
            st.session_state[chat_key].append({"role":"assistant","agent":r["agent"],
                                               "content":r.get("answer","")})

# =====================================================================
# ROUTE
# =====================================================================
if st.session_state.auth is None:
    render_login()
elif st.session_state.auth["role"] == "admin":
    render_admin_dashboard()
else:
    render_student_dashboard()
