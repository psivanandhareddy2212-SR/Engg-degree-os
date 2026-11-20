import json
import logging
from supabase import create_client
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from google import genai

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

@st.cache_data(ttl=300, show_spinner=False)
def load_data(key, user_id):
    path = DATA_DIR / FILES[key]

    try:
        response = (
            db.table("degree_os_data")
            .select("data")
            .eq("dataset", key)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        rows = response.data or []

        if rows:
            records = rows[0]["data"]
            df = pd.DataFrame(records)
        else:
            if path.exists():
                df = pd.read_csv(path)
            else:
                df = pd.DataFrame(columns=DEFAULTS[key])

            # Save initial or migrated data.
            # Do not call save_data() from this cached function.
            records = json.loads(
                df.to_json(orient="records", date_format="iso")
            )
            db.table("degree_os_data").upsert(
                {
                    "user_id": user_id,
                    "dataset": key,
                    "data": records
                },
                on_conflict="user_id,dataset"
            ).execute()

        for col in DEFAULTS[key]:
            if col not in df.columns:
                df[col] = ""

        return df[
            DEFAULTS[key] +
            [c for c in df.columns if c not in DEFAULTS[key]]
        ]

    except Exception:
        logger.exception(f"Could not load {key} from Supabase")
        raise
def save_data(key, df):
    try:
        records = json.loads(
            df.to_json(orient="records", date_format="iso")
        )

        db.table("degree_os_data").upsert(
            {
                "user_id": str(session.user.id),
                "dataset": key,
                "data": records
            },
            on_conflict="user_id,dataset"
        ).execute()

        load_data.clear()

        st.success(f"Saved {FILES[key]} to Supabase!")

    except Exception:
        logger.exception(f"Could not save {key} to Supabase")
        st.error(f"Could not save {FILES[key]}.")
def as_date(series):
    return pd.to_datetime(series, errors="coerce").dt.date

st.set_page_config(page_title="My Engineering Degree OS", page_icon="🎓", layout="wide")
logger = logging.getLogger(__name__)

# Read Supabase configuration
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_PUBLISHABLE_KEY"]
except (FileNotFoundError, KeyError):
    st.error("Check your Supabase settings in secrets.toml.")
    st.stop()

# Create a separate Supabase client for each browser session
try:
    if "_supabase" not in st.session_state:
        st.session_state["_supabase"] = create_client(url, key)

    db = st.session_state["_supabase"]
    session = db.auth.get_session()

except Exception:
    logger.exception("Supabase connection failed")
    st.error("Could not connect to Supabase. Check your settings.")
    st.stop()

# Require sign-in
if session is None:
    st.header("Engineering Degree OS")
    st.subheader("Sign in")

    with st.form("sign_in", clear_on_submit=True):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        sign_in = st.form_submit_button("Sign in")

    if sign_in:
        if not email.strip() or not password:
            st.warning("Enter your email and password.")
        else:
            try:
                result = db.auth.sign_in_with_password({
                    "email": email.strip(),
                    "password": password
                })

                if result.session is not None:
                    st.rerun()
                else:
                    st.error("No session created. Check your account.")

            except Exception:
                logger.exception("Sign in failed")
                st.error("Sign in failed. Check your email and password.")

    st.stop()

st.sidebar.caption(f"Signed in as {session.user.email}")

if st.sidebar.button("Sign out"):
    try:
        db.auth.sign_out({"scope": "local"})
    except Exception:
        logger.exception("Sign out failed")

    st.session_state.pop("_supabase", None)
    st.rerun()

st.title("🎓 My Engineering Degree OS")
st.caption("Your Semester 1–8 academic command centre")

with st.spinner("Loading your Engineering Degree OS..."):
    data = {
        key: load_data(key, str(session.user.id))
        for key in FILES
    }

# Create starter checklist only when no saved checklist exists.
if data["plan"].empty and not (DATA_DIR / FILES["plan"]).exists():
    data["plan"] = pd.DataFrame(
        [
            ["Semester Preparation", "Download current syllabus", str(date.today()), "Not Started", ""],
            ["Assessments", "Prepare for the next internal assessment", str(date.today() + timedelta(days=7)), "Not Started", ""],
            ["Projects", "Choose a mini-project problem statement", str(date.today() + timedelta(days=14)), "Not Started", ""],
            ["Documents", "Organise marksheets and certificates", str(date.today() + timedelta(days=30)), "Not Started", ""],
            ["Skills", "Complete one programming practice session", str(date.today() + timedelta(days=5)), "Not Started", ""],
            ["Internship/Placement", "Update resume", str(date.today() + timedelta(days=45)), "Not Started", ""],
        ],
        columns=DEFAULTS["plan"]
    )
    save_data("plan", data["plan"])

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
st.sidebar.caption("Your academic data is securely stored in Supabase.")

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
    c4.metric("percentage", f"{score_pct:.1f}%")
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
    cols = st.columns(4)

    for i in range(1, 9):
        semester_data = sem[sem["semester"] == i]

        with cols[(i - 1) % 4]:
            if not semester_data.empty:
                row = semester_data.iloc[0]
                status = str(row["status"])
                total = float(row["total_credits"])
                done = float(row["completed_credits"])
                count = int((courses["semester"] == i).sum())
            else:
                status = "No data entered"
                total = 0
                done = 0
                count = 0

            st.metric(f"Semester {i}", status)
            st.caption(f"{done:g} / {total:g} credits")
            st.caption(f"{count} courses")
            st.progress(min(max(done / total, 0), 1) if total else 0.0)

elif page == "Courses & Syllabus":
    st.header("Courses & Syllabus")

    if courses.empty:
        st.warning("No course records found. Add courses in Data Admin.")
    else:
        selected = st.selectbox("Select semester", list(range(1, 9)))
        view = courses[courses["semester"] == selected]

        st.subheader(f"Semester {selected} Courses")

        if view.empty:
            st.info("No courses have been added for this semester yet.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total courses", len(view))
            c2.metric("Total credits", float(view["credits"].sum()))
            c3.metric(
                "Completed courses",
                int(view["status"].astype(str).str.lower().eq("completed").sum())
            )

            st.dataframe(view, use_container_width=True, hide_index=True)

            st.subheader("Course syllabus and topics")
            for _, row in view.iterrows():
                with st.expander(f"{row['course_code']} – {row['course_name']}"):
                    st.write("**Credits:**", row["credits"])
                    st.write("**Status:**", row["status"])
                    st.write("**Syllabus / Topics:**")
                    st.write(row["syllabus"])

elif page == "University Syllabus":
    st.header("University Syllabus")
    st.subheader("Engineering Degree Programme")

    st.write("Programme duration: 4 years")
    st.write("Total semesters: 8")

    total_credits = float(sem["total_credits"].sum()) if not sem.empty else 0
    st.metric("Expected credits entered in Degree OS", total_credits)

    st.info(
        "Enter the verified university curriculum details and refer to "
        "your official university syllabus for regulations."
    )

    st.subheader("Syllabus Reference")
    st.text_input(
        "University syllabus source / reference",
        key="university_syllabus_reference",
        placeholder="Paste official university syllabus URL or document reference"
    )

    st.caption(
        "Official regulations, credit requirements and syllabus content "
        "must be verified against your university's published documents."
    )

elif page == "Academic / Leave Calendar":
    st.header("Academic / Leave Calendar")

    if calendar.empty:
        st.warning("No calendar records found. Add records in Data Admin.")
    else:
        c1, c2 = st.columns(2)

        years = ["All"] + sorted(
            calendar["academic_year"].dropna().astype(str).unique().tolist()
        )

        semesters = ["All"] + list(range(1, 9))

        with c1:
            year = st.selectbox("Academic year", years)

        with c2:
            semester = st.selectbox("Semester", semesters)

        view = calendar.copy()

        if year != "All":
            view = view[view["academic_year"].astype(str) == year]

        if semester != "All":
            view = view[view["semester"] == semester]

        event_types = ["All"] + sorted(
            view["event_type"].dropna().astype(str).unique().tolist()
        )

        event_filter = st.selectbox("Event type", event_types)

        if event_filter != "All":
            view = view[
                view["event_type"].astype(str) == event_filter
            ]

        view = view.sort_values("date_parsed", na_position="last")

        st.metric("Total calendar events", len(view))

        if view.empty:
            st.info("No events found for the selected filters.")
        else:
            st.dataframe(
                view.drop(columns=["date_parsed"], errors="ignore"),
                use_container_width=True,
                hide_index=True
            )

elif page == "Internal Assessments":
    st.header("Internal Assessments")

    if assessments.empty:
        st.warning("No assessment records found. Add records in Data Admin.")
    else:
        c1, c2 = st.columns(2)

        with c1:
            selected = st.selectbox(
                "Filter by semester",
                ["All"] + list(range(1, 9))
            )

        with c2:
            types = ["All"] + sorted(
                assessments["assessment_type"].dropna().astype(str).unique().tolist()
            )
            assessment_type = st.selectbox("Assessment type", types)

        view = assessments.copy()

        if selected != "All":
            view = view[view["semester"] == selected]

        if assessment_type != "All":
            view = view[
                view["assessment_type"].astype(str) == assessment_type
            ]

        view = view.sort_values("date_parsed", na_position="last")

        st.metric("Total assessments", len(view))

        if view.empty:
            st.info("No assessments match the selected filters.")
        else:
            upcoming = view[
                view["date_parsed"].notna()
                & (view["date_parsed"].dt.date >= date.today())
            ]

            st.metric("Upcoming assessments", len(upcoming))

            st.dataframe(
                view.drop(columns=["date_parsed"], errors="ignore"),
                use_container_width=True,
                hide_index=True
            )
elif page == "Semesters 1–8":
    st.header("Semesters 1–8")
    cols = st.columns(4)

    for i in range(1, 9):
        semester_data = sem[sem["semester"] == i]

        with cols[(i - 1) % 4]:
            if not semester_data.empty:
                row = semester_data.iloc[0]
                status = str(row["status"])
                total = float(row["total_credits"])
                done = float(row["completed_credits"])
                count = int((courses["semester"] == i).sum())
            else:
                status = "No data entered"
                total = 0
                done = 0
                count = 0

            st.metric(f"Semester {i}", status)
            st.caption(f"{done:g} / {total:g} credits")
            st.caption(f"{count} courses")
            st.progress(min(max(done / total, 0), 1) if total else 0.0)

elif page == "Courses & Syllabus":
    st.header("Courses & Syllabus")

    if courses.empty:
        st.warning("No course records found. Add courses in Data Admin.")
    else:
        selected = st.selectbox("Select semester", list(range(1, 9)))
        view = courses[courses["semester"] == selected]

        st.subheader(f"Semester {selected} Courses")

        if view.empty:
            st.info("No courses have been added for this semester yet.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total courses", len(view))
            c2.metric("Total credits", float(view["credits"].sum()))
            c3.metric(
                "Completed courses",
                int(view["status"].astype(str).str.lower().eq("completed").sum())
            )

            st.dataframe(view, use_container_width=True, hide_index=True)

            st.subheader("Course syllabus and topics")
            for _, row in view.iterrows():
                with st.expander(f"{row['course_code']} – {row['course_name']}"):
                    st.write("**Credits:**", row["credits"])
                    st.write("**Status:**", row["status"])
                    st.write("**Syllabus / Topics:**")
                    st.write(row["syllabus"])

elif page == "University Syllabus":
    st.header("University Syllabus")
    st.subheader("Engineering Degree Programme")

    st.write("Programme duration: 4 years")
    st.write("Total semesters: 8")

    total_credits = float(sem["total_credits"].sum()) if not sem.empty else 0
    st.metric("Expected credits entered in Degree OS", total_credits)

    st.info(
        "Enter the verified university curriculum details and refer to "
        "your official university syllabus for regulations."
    )

    st.subheader("Syllabus Reference")
    st.text_input(
        "University syllabus source / reference",
        key="university_syllabus_reference",
        placeholder="Paste official university syllabus URL or document reference"
    )

    st.caption(
        "Official regulations, credit requirements and syllabus content "
        "must be verified against your university's published documents."
    )

elif page == "Academic / Leave Calendar":
    st.header("Academic / Leave Calendar")

    if calendar.empty:
        st.warning("No calendar records found. Add records in Data Admin.")
    else:
        c1, c2 = st.columns(2)

        years = ["All"] + sorted(
            calendar["academic_year"].dropna().astype(str).unique().tolist()
        )

        semesters = ["All"] + list(range(1, 9))

        with c1:
            year = st.selectbox("Academic year", years)

        with c2:
            semester = st.selectbox("Semester", semesters)

        view = calendar.copy()

        if year != "All":
            view = view[view["academic_year"].astype(str) == year]

        if semester != "All":
            view = view[view["semester"] == semester]

        event_types = ["All"] + sorted(
            view["event_type"].dropna().astype(str).unique().tolist()
        )

        event_filter = st.selectbox("Event type", event_types)

        if event_filter != "All":
            view = view[
                view["event_type"].astype(str) == event_filter
            ]

        view = view.sort_values("date_parsed", na_position="last")

        st.metric("Total calendar events", len(view))

        if view.empty:
            st.info("No events found for the selected filters.")
        else:
            st.dataframe(
                view.drop(columns=["date_parsed"], errors="ignore"),
                use_container_width=True,
                hide_index=True
            )

elif page == "Internal Assessments":
    st.header("Internal Assessments")

    if assessments.empty:
        st.warning("No assessment records found. Add records in Data Admin.")
    else:
        c1, c2 = st.columns(2)

        with c1:
            selected = st.selectbox(
                "Filter by semester",
                ["All"] + list(range(1, 9))
            )

        with c2:
            types = ["All"] + sorted(
                assessments["assessment_type"].dropna().astype(str).unique().tolist()
            )
            assessment_type = st.selectbox("Assessment type", types)

        view = assessments.copy()

        if selected != "All":
            view = view[view["semester"] == selected]

        if assessment_type != "All":
            view = view[
                view["assessment_type"].astype(str) == assessment_type
            ]

        view = view.sort_values("date_parsed", na_position="last")

        st.metric("Total assessments", len(view))

        if view.empty:
            st.info("No assessments match the selected filters.")
        else:
            upcoming = view[
                view["date_parsed"].notna()
                & (view["date_parsed"].dt.date >= date.today())
            ]

            st.metric("Upcoming assessments", len(upcoming))

            st.dataframe(
                view.drop(columns=["date_parsed"], errors="ignore"),
                use_container_width=True,
                hide_index=True
            )
elif page == "Status Tracker":
    st.header("Status Tracker")

    tracker = courses.copy()

    if "status" not in tracker.columns:
        tracker["status"] = "Not Started"

    tracker["status"] = tracker["status"].fillna("Not Started").astype(str)

    completed = tracker["status"].str.lower().isin(["completed", "complete", "done"]).sum()
    progress = tracker["status"].str.lower().isin(["in progress", "ongoing"]).sum()
    not_started = len(tracker) - completed - progress

    c1, c2, c3 = st.columns(3)
    c1.metric("Completed", int(completed))
    c2.metric("In Progress", int(progress))
    c3.metric("Not Started", int(not_started))

    if len(tracker):
        percentage = completed / len(tracker) * 100
        st.progress(percentage / 100)
        st.write(f"Overall course completion: {percentage:.1f}%")

        edited_tracker = st.data_editor(
            tracker,
            use_container_width=True,
            hide_index=True,
            key="status_tracker_editor"
        )

        if st.button("Save Status Tracker"):
            save_data("courses", edited_tracker)
            st.success("Status Tracker saved successfully.")
            st.rerun()
    else:
        st.info("No course records available. Add courses in Data Admin.")


elif page == "Scorecard":
    st.header("Scorecard")

    if not scores.empty:
        total_score = pd.to_numeric(scores["score_num"], errors="coerce").sum()
        total_max = pd.to_numeric(scores["max_num"], errors="coerce").sum()

        percentage = (total_score / total_max * 100) if total_max > 0 else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Marks", f"{total_score:g}")
        c2.metric("Maximum Marks", f"{total_max:g}")
        c3.metric("Overall Percentage", f"{percentage:.2f}%")

        st.progress(min(percentage / 100, 1.0))

        st.subheader("Assessment-wise Scorecard")
        st.dataframe(scores, use_container_width=True, hide_index=True)

        if "semester" in scores.columns:
            st.subheader("Semester-wise Performance")
            semester_scores = scores.copy()
            semester_scores["score_num"] = pd.to_numeric(
                semester_scores["score_num"], errors="coerce"
            )
            semester_scores["max_num"] = pd.to_numeric(
                semester_scores["max_num"], errors="coerce"
            )
            summary = semester_scores.groupby("semester", dropna=False).agg(
                obtained=("score_num", "sum"),
                maximum=("max_num", "sum")
            )
            summary["percentage"] = (
                summary["obtained"] / summary["maximum"] * 100
            ).fillna(0)
            st.dataframe(summary, use_container_width=True)
    else:
        st.info("No score records available. Add assessment scores in Data Admin.")

    st.caption("This percentage is based on recorded marks, not an official university CGPA.")


elif page == "Plan & Checklist":
    st.header("Plan & Checklist")

    checklist = plan.copy()

    if "item" not in checklist.columns:
        checklist["item"] = ""

    if "status" not in checklist.columns:
        checklist["status"] = "Not Started"

    if "category" not in checklist.columns:
        checklist["category"] = "General"

    if "target_date" not in checklist.columns:
        checklist["target_date"] = ""

    checklist["status"] = checklist["status"].fillna("Not Started").astype(str)

    completed = checklist["status"].str.lower().isin(
        ["completed", "complete", "done"]
    ).sum()

    pending = len(checklist) - completed

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Tasks", len(checklist))
    c2.metric("Completed Tasks", int(completed))
    c3.metric("Pending Tasks", int(pending))

    if len(checklist):
        percentage = completed / len(checklist) * 100
        st.progress(percentage / 100)
        st.write(f"Checklist completion: {percentage:.1f}%")

    st.subheader("Your Academic Checklist")

    edited_checklist = st.data_editor(
        checklist,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="plan_checklist_editor"
    )

    if st.button("Save Plan & Checklist"):
        save_data("plan", edited_checklist)
        st.success("Plan & Checklist saved successfully.")
        st.rerun()
elif page == "Ask Degree AI":
    st.header("🤖 Ask Degree AI")
    st.caption("Fast academic answers with Gemini support when needed.")

    SAFE_REPLY = "I cannot verify that from the current Degree OS data."

    # Initialise chat history
    if "degree_ai_messages" not in st.session_state:
        st.session_state.degree_ai_messages = []

    # Helpers for reading academic data
    def get_column(df, names):
        for name in names:
            if name in df.columns:
                return name
        return None

    def get_date_series(df):
        if "date_parsed" in df.columns:
            return pd.to_datetime(df["date_parsed"], errors="coerce")

        col = get_column(
            df,
            ["date", "assessment_date", "event_date", "target_date", "due_date"]
        )

        if col:
            return pd.to_datetime(df[col], errors="coerce")

        return pd.Series(pd.NaT, index=df.index)

    def local_degree_answer(question):
        q = question.lower().strip()

        # Official rules must never be invented
        if any(word in q for word in [
            "official cgpa", "cgpa formula", "sgpa formula",
            "university regulation", "official grading",
            "eligibility criteria", "official passing marks"
        ]):
            return SAFE_REPLY

        # Current semester
        if "current semester" in q:
            if sem.empty:
                return SAFE_REPLY

            status_col = get_column(sem, ["status"])
            semester_col = get_column(sem, ["semester"])

            if not semester_col:
                return SAFE_REPLY

            if status_col:
                current = sem[
                    sem[status_col].astype(str).str.lower().eq("in progress")
                ]
            else:
                current = pd.DataFrame()

            if not current.empty:
                return f"Your current semester is Semester {current.iloc[0][semester_col]}."

            return f"Your recorded semester is Semester {sem.iloc[0][semester_col]}."

        # Incomplete courses
        if "incomplete" in q or "pending courses" in q:
            if courses.empty:
                return "No course records are available."

            status_col = get_column(courses, ["status"])
            name_col = get_column(
                courses, ["course_name", "course_code", "name", "title"]
            )

            if not status_col or not name_col:
                return SAFE_REPLY

            incomplete = courses[
                ~courses[status_col].astype(str).str.lower().isin(
                    ["completed", "complete", "done"]
                )
            ]

            if incomplete.empty:
                return "All recorded courses are marked completed."

            return "Incomplete courses:\n\n" + "\n".join(
                f"- {row[name_col]} ({row[status_col]})"
                for _, row in incomplete.iterrows()
            )

        # Next assessment
        if "assessment" in q or "exam" in q or "test" in q:
            if assessments.empty:
                return "No assessment records are available."

            dates = get_date_series(assessments)
            upcoming = assessments.copy()
            upcoming["_date"] = dates

            upcoming = upcoming[
                upcoming["_date"].notna()
                & (upcoming["_date"].dt.date >= date.today())
            ].sort_values("_date")

            if upcoming.empty:
                return "No upcoming assessment is recorded."

            row = upcoming.iloc[0]
            type_col = get_column(
                upcoming, ["assessment_type", "type", "title", "name"]
            )
            course_col = get_column(
                upcoming, ["course_code", "course_name"]
            )

            result = f"Your next assessment is on {row['_date'].date()}."

            if type_col:
                result = f"Your next assessment is {row[type_col]} on {row['_date'].date()}."

            if course_col:
                result += f"\nCourse: {row[course_col]}"

            return result

        # Next holiday or leave
        if "holiday" in q or "leave" in q:
            if calendar.empty:
                return "No calendar records are available."

            dates = get_date_series(calendar)
            upcoming = calendar.copy()
            upcoming["_date"] = dates

            upcoming = upcoming[
                upcoming["_date"].notna()
                & (upcoming["_date"].dt.date >= date.today())
            ]

            type_col = get_column(
                upcoming, ["event_type", "event", "type"]
            )

            if type_col:
                upcoming = upcoming[
                    upcoming[type_col].astype(str).str.lower().str.contains(
                        "holiday|leave", na=False
                    )
                ]

            upcoming = upcoming.sort_values("_date")

            if upcoming.empty:
                return "No upcoming holiday or leave is recorded."

            row = upcoming.iloc[0]
            title_col = get_column(
                upcoming, ["title", "name", "event"]
            )

            title = row[title_col] if title_col else "Holiday / Leave"

            return f"Next recorded event: {title}\nDate: {row['_date'].date()}"

        # Checklist
        if "checklist" in q or "pending task" in q or "tasks" in q:
            if plan.empty:
                return "Your checklist has no recorded tasks."

            status_col = get_column(plan, ["status"])
            item_col = get_column(plan, ["item", "task", "title"])

            if not status_col or not item_col:
                return SAFE_REPLY

            pending = plan[
                ~plan[status_col].astype(str).str.lower().isin(
                    ["completed", "complete", "done"]
                )
            ]

            if pending.empty:
                return "All recorded checklist tasks are completed."

            return "Your pending tasks:\n\n" + "\n".join(
                f"- {item}" for item in pending[item_col].astype(str)
            )

        # Semester progress
        if "semester progress" in q or "degree progress" in q:
            if sem.empty:
                return SAFE_REPLY

            semester_col = get_column(sem, ["semester"])
            completed_col = get_column(
                sem, ["completed_credits"]
            )
            total_col = get_column(sem, ["total_credits"])

            if not completed_col or not total_col:
                return SAFE_REPLY

            completed = pd.to_numeric(
                sem[completed_col], errors="coerce"
            ).fillna(0).sum()

            total = pd.to_numeric(
                sem[total_col], errors="coerce"
            ).fillna(0).sum()

            percentage = completed / total * 100 if total else 0

            result = (
                f"Completed credits: {completed:g}\n"
                f"Total credits: {total:g}\n"
                f"Degree credit progress: {percentage:.1f}%"
            )

            if semester_col:
                result += "\n\nSemester-wise records:\n"
                result += sem[
                    [semester_col, completed_col, total_col]
                ].to_string(index=False)

            return result

        # Semester syllabus
        if "syllabus" in q:
            import re

            match = re.search(r"semester\s*(\d+)", q)

            if not match:
                return "Please specify the semester number, for example: Show my Semester 3 syllabus."

            semester_number = int(match.group(1))

            if courses.empty or "semester" not in courses.columns:
                return SAFE_REPLY

            selected = courses[
                pd.to_numeric(courses["semester"], errors="coerce")
                == semester_number
            ]

            if selected.empty:
                return f"No course records found for Semester {semester_number}."

            useful_columns = [
                c for c in [
                    "course_code", "course_name", "syllabus", "status"
                ] if c in selected.columns
            ]

            return (
                f"Semester {semester_number} syllabus:\n\n"
                + selected[useful_columns].to_string(index=False)
            )

        return None

    # Display previous conversation
    for message in st.session_state.degree_ai_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Suggested questions
    st.subheader("Try asking")

    suggestions = [
        "Which courses are incomplete?",
        "What is my next internal assessment?",
        "When is my next holiday?",
        "Show my Semester 3 syllabus.",
        "What tasks are pending in my checklist?",
        "Show my semester progress."
    ]

    cols = st.columns(3)

    for i, suggestion in enumerate(suggestions):
        if cols[i % 3].button(
            suggestion,
            key=f"degree_suggestion_{i}"
        ):
            st.session_state.degree_ai_question = suggestion

    question = st.chat_input(
        "Ask anything about your engineering degree..."
    )

    suggested_question = st.session_state.pop(
        "degree_ai_question", None
    )

    user_question = suggested_question or question

    if user_question:
        st.session_state.degree_ai_messages.append({
            "role": "user",
            "content": user_question
        })

        with st.chat_message("user"):
            st.markdown(user_question)

        # Try the fast local academic answer first
        answer = local_degree_answer(user_question)

        if answer is None:
            # Use Gemini only when local data cannot answer
            try:
                api_key = st.secrets.get("GEMINI_API_KEY", "")

                if not api_key:
                    answer = SAFE_REPLY
                else:
                    @st.cache_resource
                    def get_gemini_client(key):
                        return genai.Client(api_key=key)

                    client = get_gemini_client(api_key)

                    # Send compact academic context
                    relevant_data = {}

                    question_lower = user_question.lower()

                    if "course" in question_lower or "syllabus" in question_lower:
                        relevant_data["courses"] = courses
                        relevant_data["semesters"] = sem

                    elif "assessment" in question_lower or "exam" in question_lower:
                        relevant_data["assessments"] = assessments

                    elif "holiday" in question_lower or "leave" in question_lower:
                        relevant_data["calendar"] = calendar

                    elif "score" in question_lower or "mark" in question_lower:
                        relevant_data["scores"] = scores

                    elif "task" in question_lower or "checklist" in question_lower:
                        relevant_data["plan"] = plan

                    else:
                        relevant_data = {
                            "semesters": sem,
                            "courses": courses,
                            "calendar": calendar,
                            "assessments": assessments,
                            "scores": scores,
                            "plan": plan
                        }

                    context_parts = []

                    for name, df in relevant_data.items():
                        if not df.empty:
                            compact_df = df.drop(
                                columns=[
                                    "date_parsed", "score_num", "max_num"
                                ],
                                errors="ignore"
                            ).head(20)

                            context_parts.append(
                                f"{name.upper()}:\n"
                                + compact_df.to_csv(index=False)
                            )
                        else:
                            context_parts.append(
                                f"{name.upper()}: No records."
                            )

                    prompt = f"""
You are Degree AI for an engineering student.

Answer using ONLY the supplied academic records.
Never invent dates, marks, credits, syllabus or university rules.
For unsupported information say:
"{SAFE_REPLY}"

Today's date: {date.today().isoformat()}

ACADEMIC RECORDS:
{chr(10).join(context_parts)}

QUESTION:
{user_question}
"""

                    with st.spinner("Degree AI is preparing your answer..."):
                        response = client.models.generate_content(
                            model="gemini-3.8-flash",
                            contents=prompt
                        )

                    answer = response.text or SAFE_REPLY

            except Exception as exc:
                logger.exception("Degree AI request failed")
                answer = (
                    "Gemini is temporarily unavailable. "
                    "Please try again later. "
                    "Your saved academic data is still available in the other pages."
                )

        # Display and save the answer
        with st.chat_message("assistant"):
            st.markdown(answer)

        st.session_state.degree_ai_messages.append({
            "role": "assistant",
            "content": answer
        })

    if st.session_state.degree_ai_messages:
        if st.button("Clear chat history"):
            st.session_state.degree_ai_messages = []
            st.rerun()
elif page == "Data Admin":
    st.header("Data Admin")

    st.success("All changes are saved to your Supabase database.")

    labels = {
        "semesters": "Semesters",
        "courses": "Courses",
        "calendar": "Academic Calendar",
        "assessments": "Assessments",
        "scores": "Scores",
        "plan": "Plan & Checklist",
    }

    for key, label in labels.items():
        with st.expander(label, expanded=(key == "semesters")):
            current_df = data[key]

            edited_df = st.data_editor(
                current_df,
                num_rows="dynamic",
                use_container_width=True,
                key=f"admin_{key}"
            )

            if st.button(
                f"Save {label}",
                key=f"save_{key}"
            ):
                save_data(key, edited_df)
                st.success(f"{label} saved successfully!")
                st.rerun()

st.divider()
st.caption("Engineering Degree OS prototype • Verify official dates, syllabus, credits and grading rules with your institution.")