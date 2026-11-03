from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

FILES = {
    "semesters": "semesters.csv",
    "courses": "courses.csv",
    "calendar": "academic_calendar.csv",
    "assessments": "assessments.csv",
    "scores": "scores.csv",
    "plan": "plan_checklist.csv",
}

DEFAULTS = {
    "semesters": ["semester", "status", "total_credits", "completed_credits"],
    "courses": ["semester", "course_code", "course_name", "credits", "syllabus", "status"],
    "calendar": ["academic_year", "semester", "date", "event_type", "title"],
    "assessments": ["semester", "course_code", "assessment_type", "date", "max_marks", "status"],
    "scores": ["semester", "course_code", "assessment_type", "score", "max_marks", "grade"],
    "plan": ["category", "item", "target_date", "status", "notes"],
}

def load_data(key):
    path = DATA_DIR / FILES[key]
    if not path.exists():
        return pd.DataFrame(columns=DEFAULTS[key])
    try:
        df = pd.read_csv(path)
        for col in DEFAULTS[key]:
            if col not in df.columns:
                df[col] = ""
        return df[DEFAULTS[key] + [c for c in df.columns if c not in DEFAULTS[key]]]
    except Exception as exc:
        st.warning(f"Could not read {FILES[key]}: {exc}")
        return pd.DataFrame(columns=DEFAULTS[key])

def save_data(key, df):
    path = DATA_DIR / FILES[key]
    df.to_csv(path, index=False)
    st.success(f"Saved {FILES[key]}")

def as_date(series):
    return pd.to_datetime(series, errors="coerce").dt.date

st.set_page_config(page_title="My Engineering Degree OS", page_icon="🎓", layout="wide")

st.title("🎓 My Engineering Degree OS")
st.caption("Your Semester 1–8 academic command centre")

data = {key: load_data(key) for key in FILES}

# Ensure a starter checklist exists so the page is usable immediately.
if data["plan"].empty and not (DATA_DIR / FILES["plan"]).exists():
    data["plan"] = pd.DataFrame([
        ["Semester Preparation", "Download current syllabus", str(date.today()), "Not Started", ""],
        ["Assessments", "Prepare for the next internal assessment", str(date.today() + timedelta(days=7)), "Not Started", ""],
        ["Projects", "Choose a mini-project problem statement", str(date.today() + timedelta(days=14)), "Not Started", ""],
        ["Documents", "Organise marksheets and certificates", str(date.today() + timedelta(days=30)), "Not Started", ""],
        ["Skills", "Complete one programming practice session", str(date.today() + timedelta(days=5)), "Not Started", ""],
        ["Internship/Placement", "Update resume", str(date.today() + timedelta(days=45)), "Not Started", ""],
    ], columns=DEFAULTS["plan"])

sem = data["semesters"].copy()
courses = data["courses"].copy()
calendar = data["calendar"].copy()
assessments = data["assessments"].copy()
scores = data["scores"].copy()
plan = data["plan"].copy()

def numeric(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)

if not sem.empty:
    sem["semester"] = numeric(sem["semester"]).astype(int)
    sem["total_credits"] = numeric(sem["total_credits"])
    sem["completed_credits"] = numeric(sem["completed_credits"])
if not courses.empty:
    courses["semester"] = numeric(courses["semester"]).astype(int)
    courses["credits"] = numeric(courses["credits"])
if not assessments.empty:
    assessments["semester"] = numeric(assessments["semester"]).astype(int)
    assessments["date_parsed"] = pd.to_datetime(assessments["date"], errors="coerce")
if not calendar.empty:
    calendar["semester"] = numeric(calendar["semester"]).astype(int)
    calendar["date_parsed"] = pd.to_datetime(calendar["date"], errors="coerce")
if not scores.empty:
    scores["semester"] = numeric(scores["semester"]).astype(int)
    scores["score_num"] = numeric(scores["score"])
    scores["max_num"] = numeric(scores["max_marks"])

pages = [
    "Dashboard", "Semesters 1–8", "Courses & Syllabus", "University Syllabus",
    "Academic / Leave Calendar", "Internal Assessments", "Status Tracker",
    "Scorecard", "Plan & Checklist", "Ask Degree AI", "Data Admin"
]
page = st.sidebar.radio("Navigate", pages)
st.sidebar.divider()
st.sidebar.caption("Data is stored in editable CSV files in the data/ folder.")

if page == "Dashboard":
    st.header("Dashboard")
    current = sem[sem["status"].astype(str).str.lower().eq("in progress")] if not sem.empty else pd.DataFrame()
    current_sem = int(current.iloc[0]["semester"]) if not current.empty else (int(sem["semester"].min()) if not sem.empty else 1)
    total_credits = float(sem["total_credits"].sum()) if not sem.empty else 0
    completed_credits = float(sem["completed_credits"].sum()) if not sem.empty else 0
    completion = (completed_credits / total_credits * 100) if total_credits else 0
    score_pct = (scores["score_num"].sum() / scores["max_num"].sum() * 100) if not scores.empty and scores["max_num"].sum() else 0

    upcoming = assessments[assessments["date_parsed"].notna() & (assessments["date_parsed"].dt.date >= date.today())].sort_values("date_parsed") if not assessments.empty else pd.DataFrame()
    holidays = calendar[(calendar["date_parsed"].notna()) & (calendar["date_parsed"].dt.date >= date.today()) & calendar["event_type"].astype(str).str.lower().isin(["holiday", "leave"])] if not calendar.empty else pd.DataFrame()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current semester", current_sem)
    c2.metric("Degree credit completion", f"{completion:.1f}%")
    c3.metric("Completed credits", f"{completed_credits:g} / {total_credits:g}")
    c4.metric("Prototype score percentage", f"{score_pct:.1f}%")
    left, right = st.columns(2)
    with left:
        st.subheader("Next assessment")
        if not upcoming.empty:
            row = upcoming.iloc[0]
            st.write(f"**{row['assessment_type']} – {row['course_code']}**")
            st.write(row["date_parsed"].date().isoformat())
        else:
            st.info("No future assessment is recorded in assessments.csv.")
    with right:
        st.subheader("Next holiday / leave")
        if not holidays.empty:
            row = holidays.sort_values("date_parsed").iloc[0]
            st.write(f"**{row['title']}**")
            st.write(row["date_parsed"].date().isoformat())
        else:
            st.info("No future holiday or leave is recorded in academic_calendar.csv.")
    st.subheader("Semester progress")
    if not sem.empty:
        chart = sem.set_index("semester")[["completed_credits", "total_credits"]]
        st.bar_chart(chart)
        st.dataframe(sem, use_container_width=True, hide_index=True)
    else:
        st.warning("Add semester rows to data/semesters.csv to populate the dashboard.")

elif page == "Semesters 1–8":
    st.header("Semesters 1–8")
    if sem.empty:
        st.warning("No semester data found. Add Semester 1–8 rows to semesters.csv.")
    else:
        cols = st.columns(4)
        for i, (_, row) in enumerate(sem.sort_values("semester").iterrows()):
            with cols[i % 4]:
                total = float(row["total_credits"])
                done = float(row["completed_credits"])
                pct = done / total if total else 0
                st.metric(f"Semester {int(row['semester'])}", str(row["status"]))
                st.caption(f"{done:g} / {total:g} credits")
                st.progress(min(max(pct, 0.0), 1.0))
                count = int((courses["semester"] == int(row["semester"])).sum()) if not courses.empty else 0
                st.caption(f"{count} courses")

elif page == "Courses & Syllabus":
    st.header("Courses & Syllabus")
    if courses.empty:
        st.warning("No courses found in data/courses.csv.")
    else:
        selected = st.selectbox("Select semester", sorted(courses["semester"].unique().tolist()))
        view = courses[courses["semester"] == selected].drop(columns=[], errors="ignore")
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.subheader("Course topics")
        for _, row in view.iterrows():
            with st.expander(f"{row['course_code']} – {row['course_name']}"):
                st.write(row["syllabus"])

elif page == "University Syllabus":
    st.header("University Syllabus")
    st.write("Programme-level syllabus overview")
    st.info("This prototype does not contain a verified university regulation or complete official syllabus.")
    st.write("**Programme:** Engineering degree")
    st.write("**Duration:** 8 semesters")
    st.write("**Expected credits:** Enter the verified total from your university curriculum.")
    st.text_input("Syllabus source / reference", placeholder="Paste official university syllabus URL or document reference")
    st.caption("Do not treat sample course topics in courses.csv as the official university syllabus.")

elif page == "Academic / Leave Calendar":
    st.header("Academic / Leave Calendar")
    if calendar.empty:
        st.warning("No calendar records found in data/academic_calendar.csv.")
    else:
        years = ["All"] + sorted(calendar["academic_year"].dropna().astype(str).unique().tolist())
        year = st.selectbox("Academic year", years)
        sems = ["All"] + sorted(calendar["semester"].unique().tolist())
        semester = st.selectbox("Semester", sems)
        view = calendar.copy()
        if year != "All":
            view = view[view["academic_year"].astype(str) == year]
        if semester != "All":
            view = view[view["semester"] == semester]
        st.dataframe(view.drop(columns=["date_parsed"], errors="ignore").sort_values("date"), use_container_width=True, hide_index=True)

elif page == "Internal Assessments":
    st.header("Internal Assessments")
    if assessments.empty:
        st.warning("No assessment records found in data/assessments.csv.")
    else:
        semesters = ["All"] + sorted(assessments["semester"].unique().tolist())
        selected = st.selectbox("Filter by semester", semesters)
        view = assessments if selected == "All" else assessments[assessments["semester"] == selected]
        st.dataframe(view.drop(columns=["date_parsed"], errors="ignore").sort_values("date"), use_container_width=True, hide_index=True)

elif page == "Status Tracker":
    st.header("Status Tracker")
    if courses.empty:
        st.warning("No courses found in data/courses.csv.")
    else:
        semester = st.selectbox("Semester", sorted(courses["semester"].unique().tolist()))
        view = courses[courses["semester"] == semester].copy()
        counts = view["status"].astype(str).value_counts()
        a, b, c = st.columns(3)
        a.metric("Not Started", int(counts.get("Not Started", 0)))
        b.metric("In Progress", int(counts.get("In Progress", 0)))
        c.metric("Completed", int(counts.get("Completed", 0)))
        done = int(view["status"].astype(str).str.lower().eq("completed").sum())
        st.progress(done / len(view) if len(view) else 0)
        st.dataframe(view, use_container_width=True, hide_index=True)

elif page == "Scorecard":
    st.header("Scorecard")
    if scores.empty:
        st.warning("No marks found in data/scores.csv.")
    else:
        total = scores["score_num"].sum()
        maximum = scores["max_num"].sum()
        pct = total / maximum * 100 if maximum else 0
        st.metric("Prototype score percentage", f"{pct:.2f}%")
        st.caption("This is a simple total-score percentage, not an official university CGPA.")
        st.dataframe(scores.drop(columns=["score_num", "max_num"], errors="ignore"), use_container_width=True, hide_index=True)
        per_sem = scores.groupby("semester")[["score_num", "max_num"]].sum()
        per_sem["prototype_percentage"] = (per_sem["score_num"] / per_sem["max_num"] * 100).round(2)
        st.subheader("Semester-wise prototype percentage")
        st.dataframe(per_sem, use_container_width=True)

elif page == "Plan & Checklist":
    st.header("Plan & Checklist")
    st.caption("Edit the table, then click Save checklist. Health is calculated from target dates.")
    edited = st.data_editor(plan, num_rows="dynamic", use_container_width=True, key="plan_editor")
    if st.button("Save checklist"):
        save_data("plan", edited)
        st.rerun()
    if not edited.empty:
        dates = pd.to_datetime(edited["target_date"], errors="coerce").dt.date
        statuses = edited["status"].astype(str).str.lower()
        due_soon = sum(1 for d, s in zip(dates, statuses) if pd.notna(d) and date.today() <= d <= date.today() + timedelta(days=7) and s not in ["done", "completed"])
        overdue = sum(1 for d, s in zip(dates, statuses) if pd.notna(d) and d < date.today() and s not in ["done", "completed"])
        done = int(statuses.isin(["done", "completed"]).sum())
        x, y, z, w = st.columns(4)
        x.metric("Total items", len(edited))
        y.metric("Done", done)
        z.metric("Due soon", due_soon)
        w.metric("Overdue", overdue)

elif page == "Ask Degree AI":
    st.header("Ask Degree AI")
    st.caption("Local data-based helper. It does not use a generative AI API in this starter version.")
    question = st.text_input("Ask about courses, assessments, holidays or checklist")
    if st.button("Ask"):
        q = question.lower()
        answer = "I cannot verify that from the current Degree OS data."
        used = "No matching data"
        if any(word in q for word in ["incomplete", "left", "pending course", "not completed"]):
            if not courses.empty:
                sem_nums = [int(x) for x in range(1, 9) if f"sem {x}" in q or f"semester {x}" in q]
                subset = courses[courses["semester"].isin(sem_nums)] if sem_nums else courses
                subset = subset[~subset["status"].astype(str).str.lower().eq("completed")]
                answer = ", ".join(subset["course_name"].astype(str).tolist()) if not subset.empty else "No incomplete courses are listed."
                used = "Courses"
        elif "assessment" in q or "ia" in q:
            if not assessments.empty:
                upcoming = assessments[pd.to_datetime(assessments["date"], errors="coerce").dt.date >= date.today()].copy()
                upcoming = upcoming.sort_values("date")
                if not upcoming.empty:
                    r = upcoming.iloc[0]
                    answer = f"Next recorded assessment: {r['assessment_type']} for {r['course_code']} on {r['date']}."
                else:
                    answer = "No future assessments are listed."
                used = "Assessments"
        elif "holiday" in q or "leave" in q:
            if not calendar.empty:
                cal = calendar[calendar["event_type"].astype(str).str.lower().isin(["holiday", "leave"])].copy()
                cal = cal[pd.to_datetime(cal["date"], errors="coerce").dt.date >= date.today()].sort_values("date")
                if not cal.empty:
                    r = cal.iloc[0]
                    answer = f"Next recorded holiday/leave: {r['title']} on {r['date']}."
                else:
                    answer = "No future holidays or leave are listed."
                used = "Calendar"
        elif "topic" in q or "syllabus" in q or "data structures" in q:
            if not courses.empty:
                match = courses[courses["course_name"].astype(str).str.lower().str.contains("data structures", na=False) | courses["course_code"].astype(str).str.lower().str.contains("cs301", na=False)]
                if not match.empty:
                    answer = "; ".join(match["syllabus"].astype(str).tolist())
                    used = "Courses"
        elif "checklist" in q or "task" in q:
            if not plan.empty:
                answer = "; ".join(f"{r['item']}: {r['status']}" for _, r in plan.iterrows())
                used = "Plan"
        elif "cgpa" in q or "university rule" in q or "eligibility" in q:
            answer = "I cannot verify that from the current Degree OS data."
            used = "No verified official rule"
        st.success(answer)
        st.caption(f"Data area used: {used}")
    st.info("For Gemini-powered responses, connect an API key securely in Streamlit Secrets in a later version. Never commit API keys to GitHub.")

elif page == "Data Admin":
    st.header("Data Admin")
    st.warning("Edit a table and click its Save button. Changes are written to the matching CSV file.")
    labels = {
        "semesters": "Semesters",
        "courses": "Courses",
        "calendar": "Academic calendar",
        "assessments": "Assessments",
        "scores": "Scores",
        "plan": "Plan & checklist",
    }
    for key, label in labels.items():
        with st.expander(label, expanded=(key == "semesters")):
            current_df = data[key]
            edited_df = st.data_editor(current_df, num_rows="dynamic", use_container_width=True, key=f"admin_{key}")
            if st.button(f"Save {FILES[key]}", key=f"save_{key}"):
                save_data(key, edited_df)
                st.rerun()

st.divider()
st.caption("Engineering Degree OS prototype • Verify official dates, syllabus, credits and grading rules with your institution.")
