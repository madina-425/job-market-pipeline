"""
dashboard/app.py
Streamlit dashboard for the Job Market Analytics Pipeline.
Run: streamlit run dashboard/app.py
"""
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KZ Job Market Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Kazakhstan Job Market Analytics")
st.caption("Data Engineer · Data Analyst · ML Engineer roles — updated daily")


# ── DB connection ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_engine():
    url = (
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', 5432)}/{os.environ.get('DB_NAME', 'jobmarket')}"
    )
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=3600)
def query(sql: str) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn)


# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    role_filter = st.multiselect(
        "Role",
        ["Data Analyst", "Data Engineer", "ML Engineer"],
        default=["Data Analyst", "Data Engineer", "ML Engineer"],
    )
    seniority_filter = st.multiselect(
        "Seniority",
        ["junior", "mid", "senior", "unknown"],
        default=["junior", "mid", "senior"],
    )
    remote_filter = st.multiselect(
        "Work type",
        ["remote", "hybrid", "on-site", "unknown"],
        default=["remote", "hybrid", "on-site"],
    )

role_sql = "','".join(role_filter)
seniority_sql = "','".join(seniority_filter)
remote_sql = "','".join(remote_filter)

base_where = f"""
    WHERE role_category IN ('{role_sql}')
      AND seniority IN ('{seniority_sql}')
      AND remote_type IN ('{remote_sql}')
      AND published_at >= now() - INTERVAL '90 days'
"""

# ── KPI row ───────────────────────────────────────────────────────────────────
kpi = query(f"SELECT COUNT(*) AS total, AVG(salary_usd_mid) AS avg_sal FROM jobs {base_where}")
total_jobs = int(kpi.iloc[0]["total"])
avg_sal = kpi.iloc[0]["avg_sal"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total postings (90d)", f"{total_jobs:,}")
col2.metric("Avg salary (USD/mo)", f"${avg_sal:,.0f}" if avg_sal else "N/A")

remote_pct = query(f"""
    SELECT remote_type, COUNT(*) AS n FROM jobs {base_where}
    GROUP BY remote_type
""")
if not remote_pct.empty:
    r = remote_pct.set_index("remote_type")["n"]
    pct = round(r.get("remote", 0) / r.sum() * 100)
    col3.metric("Remote %", f"{pct}%")

col4.metric("Sources", "HeadHunter · Djinni · RemoteOK")

st.divider()

# ── Row 1: skills + salary ────────────────────────────────────────────────────
left, right = st.columns(2)

with left:
    st.subheader("Top 25 most demanded skills")
    skill_role = st.selectbox("Filter by role", ["All"] + role_filter, key="skill_role")
    where_role = f"AND role_category = '{skill_role}'" if skill_role != "All" else ""
    skills_df = query(f"""
        SELECT skill, SUM(frequency) AS freq
        FROM mv_skill_demand
        WHERE 1=1 {where_role}
        GROUP BY skill ORDER BY freq DESC LIMIT 25
    """)
    if not skills_df.empty:
        fig = px.bar(
            skills_df, x="freq", y="skill", orientation="h",
            labels={"freq": "Job postings", "skill": ""},
            color="freq", color_continuous_scale="teal",
        )
        fig.update_layout(
            showlegend=False, coloraxis_showscale=False,
            height=500, margin=dict(l=0, r=0, t=0, b=0),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No skill data yet — run the pipeline first.")

with right:
    st.subheader("Salary distribution by role")
    sal_df = query(f"""
        SELECT role_category, seniority, salary_usd_mid
        FROM jobs {base_where} AND salary_usd_mid IS NOT NULL
    """)
    if not sal_df.empty:
        fig = px.box(
            sal_df, x="role_category", y="salary_usd_mid",
            color="seniority",
            labels={"salary_usd_mid": "Monthly salary (USD)", "role_category": ""},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=500, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No salary data yet.")

st.divider()

# ── Row 2: trends + city ──────────────────────────────────────────────────────
left2, right2 = st.columns(2)

with left2:
    st.subheader("Posting volume — last 30 days")
    vol_df = query(f"""
        SELECT DATE_TRUNC('day', published_at)::date AS day,
               role_category, COUNT(*)::INT AS n
        FROM jobs {base_where}
          AND published_at >= now() - INTERVAL '30 days'
        GROUP BY day, role_category ORDER BY day
    """)
    if not vol_df.empty:
        fig = px.line(
            vol_df, x="day", y="n", color="role_category",
            labels={"n": "Postings", "day": "", "role_category": "Role"},
        )
        fig.update_layout(height=380, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

with right2:
    st.subheader("Top hiring cities")
    city_df = query(f"""
        SELECT location, COUNT(*)::INT AS n
        FROM jobs {base_where} AND location IS NOT NULL
        GROUP BY location ORDER BY n DESC LIMIT 15
    """)
    if not city_df.empty:
        fig = px.bar(
            city_df, x="n", y="location", orientation="h",
            labels={"n": "Postings", "location": ""},
            color="n", color_continuous_scale="blues",
        )
        fig.update_layout(
            showlegend=False, coloraxis_showscale=False,
            height=380, margin=dict(l=0, r=0, t=0, b=0),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Row 3: companies + remote ─────────────────────────────────────────────────
left3, right3 = st.columns(2)

with left3:
    st.subheader("Top hiring companies")
    comp_df = query(f"""
        SELECT company, COUNT(*) AS n
        FROM jobs {base_where} AND company IS NOT NULL
        GROUP BY company ORDER BY n DESC LIMIT 15
    """)
    if not comp_df.empty:
        st.dataframe(
            comp_df.rename(columns={"company": "Company", "n": "Open positions"}),
            use_container_width=True, hide_index=True,
        )

with right3:
    st.subheader("Work type breakdown")
    rt_df = query(f"""
        SELECT remote_type, COUNT(*)::INT AS n
        FROM jobs {base_where}
        GROUP BY remote_type
    """)
    if not rt_df.empty:
        fig = px.pie(
            rt_df, names="remote_type", values="n",
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

# ── Raw data explorer ─────────────────────────────────────────────────────────
with st.expander("📋 Browse raw job postings"):
    raw_df = query(f"""
        SELECT title, company, location, role_category, seniority,
               remote_type, salary_usd_mid, published_at, source, url
        FROM jobs {base_where}
        ORDER BY published_at DESC LIMIT 200
    """)
    st.dataframe(raw_df, use_container_width=True, hide_index=True)
