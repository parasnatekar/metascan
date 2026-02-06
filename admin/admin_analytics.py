# admin/admin_analytics.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from collections import Counter
from datetime import datetime, timedelta, timezone

from db import db, collection


# -------------------------
# Config (safe defaults)
# -------------------------
# You can change this later to your actual server/storage capacity.
ESTIMATED_STORAGE_CAPACITY_GB = 5.0

users_col = db["users"]

# Optional collections (will work even if empty / not created yet)
admin_logs_col = db["admin_logs"]          # audit trail (you already started this)
auth_logs_col = db["auth_logs"]            # failed logins / login history (optional)
perf_logs_col = db["perf_logs"]            # pipeline timing logs (optional)
search_logs_col = db["search_logs"]        # search intelligence logs (optional)

# GridFS default bucket collections (GridFS(db) uses "fs" by default)
fs_files_col = db["fs.files"]


# -------------------------
# Helpers
# -------------------------
def to_utc(dt):
    """Normalize mixed naive/aware datetimes to UTC-aware."""
    if not dt:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def fmt_dt(dt: datetime) -> str:
    dt = to_utc(dt)
    if not dt:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def section_header(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div style="
            background: rgba(20, 22, 28, 0.65);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 16px 18px;
            margin: 10px 0 14px 0;
            backdrop-filter: blur(10px);
        ">
            <div style="font-size: 20px; font-weight: 800;">{title}</div>
            <div style="color:#9CA3AF; margin-top:4px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def small_card(label: str, value: str, hint: str = ""):
    st.markdown(
        f"""
        <div style="
            background: rgba(30,33,40,0.62);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 14px 14px;
            height: 100%;
            box-shadow: 0 12px 30px rgba(0,0,0,0.35);
        ">
            <div style="color:#9CA3AF; font-size: 12px; letter-spacing:0.2px;">{label}</div>
            <div style="font-size: 24px; font-weight: 800; margin-top:6px;">{value}</div>
            <div style="color:#9CA3AF; font-size: 12px; margin-top:6px;">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -------------------------
# Main
# -------------------------
def show_admin_analytics():
    st.title("🛡️ Admin Intelligence")
    st.caption("Infrastructure • Engagement • Data Quality • Search Intelligence • Security")

    # Load core data
    users = list(users_col.find({}))
    papers = list(collection.find({}))

    df_users = pd.DataFrame(users)
    df_papers = pd.DataFrame(papers)

    now = datetime.now(timezone.utc)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # =========================================================
    # 1) System Health & Infrastructure
    # =========================================================
    section_header(
        "System Health & Infrastructure",
        "Monitor storage pressure, pipeline performance, and database activity patterns.",
    )

    # ---- GridFS Storage Load (Gauge) ----
    fs_total_bytes = 0
    try:
        # sum all GridFS file lengths
        pipeline = [{"$group": {"_id": None, "bytes": {"$sum": "$length"}}}]
        agg = list(fs_files_col.aggregate(pipeline))
        fs_total_bytes = safe_int(agg[0]["bytes"], 0) if agg else 0
    except Exception:
        fs_total_bytes = 0

    used_gb = fs_total_bytes / (1024 ** 3)
    cap_gb = float(ESTIMATED_STORAGE_CAPACITY_GB)
    pct = (used_gb / cap_gb * 100) if cap_gb > 0 else 0.0
    pct = max(0.0, min(100.0, pct))

    c1, c2, c3 = st.columns([2, 1, 1])

    with c1:
        fig_gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=used_gb,
                number={"suffix": " GB"},
                gauge={
                    "axis": {"range": [0, cap_gb]},
                    "bar": {"color": "rgba(56,189,248,0.95)"},
                    "bgcolor": "rgba(0,0,0,0)",
                    "steps": [
                        {"range": [0, cap_gb * 0.6], "color": "rgba(34,197,94,0.22)"},
                        {"range": [cap_gb * 0.6, cap_gb * 0.85], "color": "rgba(245,158,11,0.22)"},
                        {"range": [cap_gb * 0.85, cap_gb], "color": "rgba(239,68,68,0.22)"},
                    ],
                },
                title={"text": "GridFS Storage Load"},
            )
        )
        fig_gauge.update_layout(
            height=260,
            margin=dict(l=20, r=20, t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

    with c2:
        small_card("Storage Utilization", f"{pct:.1f}%", f"Capacity baseline: {cap_gb:.1f} GB")
    with c3:
        orphan_hint = "See Data Quality section"
        small_card("Binary Store", f"{used_gb:.2f} GB", orphan_hint)

    st.markdown("---")

    # ---- API & Processing Latency (Line Chart) ----
    st.subheader("⏱️ Processing Latency (PDF → Enrich → Recommend)")

    perf_rows = []
    try:
        perf_rows = list(
            perf_logs_col.find(
                {},
                {"_id": 0, "ts": 1, "stage": 1, "ms": 1, "meta": 1}
            ).sort("ts", -1).limit(2000)
        )
    except Exception:
        perf_rows = []

    if not perf_rows:
        st.info(
            "No processing latency logs yet. Upload a PDF after enabling log_perf(...) "
            "to populate `perf_logs`."
        )    
    else:
        df_perf = pd.DataFrame(perf_rows)
        df_perf["ts"] = pd.to_datetime(df_perf["ts"], errors="coerce", utc=True)
        df_perf = df_perf.dropna(subset=["ts", "stage", "ms"])

        # last 30d
        df_perf = df_perf[df_perf["ts"] >= pd.Timestamp(last_30d)]
        if df_perf.empty:
            st.info("No perf logs in the last 30 days.")
        else:
            # ✅ make "day" a real datetime (fixes weird 23:59 labels)
            df_perf["day"] = df_perf["ts"].dt.floor("D")

            # stage filter (cleaner UI)
            stages = sorted(df_perf["stage"].unique().tolist())
            selected_stage = st.selectbox("Stage", ["all"] + stages, index=0)

            if selected_stage != "all":
                df_perf = df_perf[df_perf["stage"] == selected_stage]

            daily = (
                df_perf.groupby(["day", "stage"])["ms"]
                .mean()
                .reset_index()
                .sort_values("day")
            )

            fig_lat = go.Figure()

            for stage in sorted(daily["stage"].unique()):
                s = daily[daily["stage"] == stage]
                fig_lat.add_trace(
                    go.Scatter(
                        x=s["day"],
                        y=s["ms"],
                        mode="lines+markers",
                        name=str(stage),
                        hovertemplate="Day=%{x|%Y-%m-%d}<br>Avg=%{y:.0f} ms (~%{customdata:.2f} s)<extra></extra>",
                        customdata=(s["ms"] / 1000.0),
                    )
                )

            fig_lat.update_layout(
                height=340,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Day (UTC)",
                yaxis_title="Average time (ms)",
                legend_title="Stage",
            )

            st.plotly_chart(fig_lat, use_container_width=True)

            # quick stats table
            st.markdown("**Last 10 events (raw):**")
            show_cols = ["ts", "stage", "ms"]
            if "meta" in df_perf.columns:
                show_cols.append("meta")
            st.dataframe(df_perf.sort_values("ts", ascending=False)[show_cols].head(10), use_container_width=True)
            

    st.markdown("---")
    # 2) User Management & Engagement
    section_header(
        "User Management & Engagement",
        "Analyze platform usage patterns and identify power users / inactivity.",
    )

    # Active vs inactive users
    active_7d = 0
    inactive = 0
    unknown_activity = 0

    for u in users:
        ll = to_utc(u.get("last_login"))
        if ll is None:
            unknown_activity += 1
        elif ll >= last_7d:
            active_7d += 1
        else:
            inactive += 1

    # Contribution leaderboard (top contributors)
    uploads_by_user = Counter()
    for p in papers:
        uploader = p.get("uploaded_by")
        if uploader:
            uploads_by_user[str(uploader)] += 1

    top_contrib = uploads_by_user.most_common(10)

    # Unique logins per day (auth_logs) fallback: last_login exists only per user, so cannot build trend without logs.
    auth_rows = []
    try:
        auth_rows = list(
            auth_logs_col.find(
                {},
                {"_id": 0, "ts": 1, "email": 1, "success": 1}
            ).sort("ts", -1).limit(2000)
        )
    except Exception:
        auth_rows = []

    cA, cB = st.columns([1, 2])

    with cA:
        fig_donut = go.Figure(go.Pie(
            labels=["Active (7d)", "Inactive", "Unknown"],
            values=[active_7d, inactive, unknown_activity],
            hole=0.62
        ))
        fig_donut.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
        )
        st.plotly_chart(fig_donut, use_container_width=True)
        st.caption("Active = users whose `last_login` is within 7 days (UTC).")

    with cB:
        st.subheader("🏅 Top Contributors (by uploads)")
        if top_contrib:
            for rank, (email, count) in enumerate(top_contrib, start=1):
                st.markdown(
                    f"""
                    <div style="
                        display:flex; justify-content:space-between; align-items:center;
                        background: rgba(30,33,40,0.55);
                        border: 1px solid rgba(255,255,255,0.06);
                        border-radius: 14px;
                        padding: 10px 12px;
                        margin-bottom: 8px;
                    ">
                        <div>
                            <span style="opacity:0.9; font-weight:800;">#{rank}</span>
                            <span style="margin-left:10px; font-family:monospace;">{email}</span>
                        </div>
                        <div style="font-weight:800;">📤 {count}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("No uploads tracked yet (missing `uploaded_by` fields).")

    st.markdown("---")
    st.subheader("📅 Unique Logins per Day (Usage Rhythm)")

    if auth_rows:
        df_auth = pd.DataFrame(auth_rows)
        df_auth["ts"] = pd.to_datetime(df_auth["ts"], errors="coerce", utc=True)
        df_auth = df_auth.dropna(subset=["ts", "email"])
        df_auth = df_auth[df_auth["ts"] >= pd.Timestamp(last_30d)]

        # successful logins only
        df_auth = df_auth[df_auth.get("success", True) == True]  # noqa: E712

        if not df_auth.empty:
            # ✅ use proper datetime day (not python date) to avoid weird x-axis labels
            df_auth["day"] = df_auth["ts"].dt.floor("D")

            uniq = (
                df_auth.groupby("day")["email"]
                .nunique()
                .reset_index(name="unique_logins")
                .sort_values("day")
            )

            # ✅ fill missing days so chart looks consistent
            all_days = pd.date_range(
                start=uniq["day"].min(),
                end=uniq["day"].max(),
                freq="D",
                tz="UTC"
            )
            uniq = uniq.set_index("day").reindex(all_days, fill_value=0).rename_axis("day").reset_index()

            # ✅ optional: rolling avg (pro look)
            uniq["roll7"] = uniq["unique_logins"].rolling(7, min_periods=1).mean()

            fig_login = go.Figure()

            # Bars
            fig_login.add_trace(go.Bar(
                x=uniq["day"],
                y=uniq["unique_logins"],
                name="Unique logins",
                hovertemplate="Day: %{x|%Y-%m-%d}<br>Unique logins: %{y}<extra></extra>",
                opacity=0.9
            ))

            # Rolling average line
            fig_login.add_trace(go.Scatter(
                x=uniq["day"],
                y=uniq["roll7"],
                name="7-day avg",
                mode="lines+markers",
                hovertemplate="Day: %{x|%Y-%m-%d}<br>7-day avg: %{y:.2f}<extra></extra>"
            ))

            fig_login.update_layout(
                height=320,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                xaxis=dict(
                    title="Day (UTC)",
                    type="date",
                    tickformat="%b %d",
                    showgrid=False
                ),
                yaxis=dict(
                    title="Unique logins",
                    rangemode="tozero",
                    gridcolor="rgba(255,255,255,0.08)"
                ),
            )

            st.plotly_chart(fig_login, use_container_width=True)

            # small summary (super useful)
            st.caption(
                f"Total days tracked: **{len(uniq)}** • "
                f"Max daily logins: **{int(uniq['unique_logins'].max())}** • "
                f"Avg/day: **{uniq['unique_logins'].mean():.2f}**"
            )
        else:
            st.info("No login events in the last 30 days.")
    else:
         st.info(
             "No `auth_logs` data yet. Optional: log auth attempts to `auth_logs` "
             "(ts, email, success) to enable login rhythm analytics."
         )

    st.markdown("---")

    # =========================================================
    # 4) Search & Discovery Intelligence
    # =========================================================
    section_header(
        "Search & Discovery Intelligence",
        "Understand what researchers search for, gaps in coverage, and internal interest signals.",
    )

    # ---- Hot Search Terms / Zero-result queries ----
    st.subheader("Hot Search Terms & Zero-result Queries")

    search_rows = []
    try:
        search_rows = list(
            search_logs_col.find(
                {},
                {"_id": 0, "ts": 1, "email": 1, "query": 1, "results_count": 1}
            ).sort("ts", -1).limit(2000)
        )
    except Exception:
        search_rows = []

    if search_rows:
        df_s = pd.DataFrame(search_rows)
        df_s["ts"] = pd.to_datetime(df_s["ts"], errors="coerce", utc=True)
        df_s = df_s.dropna(subset=["ts", "query"])
        df_s = df_s[df_s["ts"] >= pd.Timestamp(last_30d)]

        # Normalize query tokens lightly (admin-friendly)
        def norm(q):
            q = str(q).strip().lower()
            q = " ".join(q.split())
            return q[:120]

        df_s["q"] = df_s["query"].apply(norm)

        hot = df_s["q"].value_counts().head(12).reset_index()
        hot.columns = ["query", "count"]

        cS1, cS2 = st.columns(2)

        with cS1:
            fig_hot = go.Figure(go.Bar(
                x=hot["count"][::-1],
                y=hot["query"][::-1],
                orientation="h",
            ))
            fig_hot.update_layout(
                height=360,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Search frequency (30d)",
                yaxis_title="",
            )
            st.plotly_chart(fig_hot, use_container_width=True)

        with cS2:
            zeros = df_s[df_s.get("results_count", 1) == 0]
            st.markdown("**Zero-result queries (30d)**")
            if not zeros.empty:
                z = zeros["q"].value_counts().head(15)
                for q, ct in z.items():
                    st.warning(f"`{q}` — {ct} time(s)")
                st.caption("These are collection gaps. Consider ingesting papers for these topics.")
            else:
                st.success("No zero-result queries in the last 30 days.")
    else:
        st.info(
            "No search logs yet. Optional: log searches to `search_logs` "
            "(ts, email, query, results_count) inside your Search button flow."
        )

    st.markdown("---")

    # ---- Bookmark Density (global trends) ----
    st.subheader("⭐ Bookmark Density (Organization Interest)")

    bookmark_counts = Counter()
    for u in users:
        for pid in u.get("bookmarks", []):
            bookmark_counts[str(pid)] += 1

    if bookmark_counts:
        top = bookmark_counts.most_common(8)
        for pid, count in top:
            paper = None
            try:
                # Try lookup by ObjectId-like strings
                from bson import ObjectId  # local import to avoid unused in some environments
                paper = collection.find_one({"_id": ObjectId(pid)})
            except Exception:
                paper = collection.find_one({"_id": pid}) if pid else None

            title = paper.get("title", "Untitled") if paper else f"Paper ID {pid}"
            st.markdown(
                f"""
                <div style="
                    background: rgba(30,33,40,0.55);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-radius: 14px;
                    padding: 10px 12px;
                    margin-bottom: 8px;
                ">
                    <div style="font-weight:800;">{title}</div>
                    <div style="color:#9CA3AF; margin-top:4px;">⭐ Bookmarks: <b>{count}</b></div>
                </div>
                """,
                unsafe_allow_html=True
            )
        st.caption("Shows which papers/topics are trending across all users.")
    else:
        st.info("No bookmarks yet.")
    st.markdown("---")
    # =========================================================
    # 5) Security & Access Logs
    section_header(
        "Security & Access Logs",
        "Monitor failed logins and administrative actions for integrity and accountability.",
    )

    # ---- Failed Login Attempts ----
    st.subheader("🔒 Failed Login Attempts (recent)")

    if auth_rows:
        df_auth = pd.DataFrame(auth_rows)
        df_auth["ts"] = pd.to_datetime(df_auth["ts"], errors="coerce", utc=True)
        df_auth = df_auth.dropna(subset=["ts", "email"])

        failed = df_auth[df_auth.get("success", True) == False]  # noqa: E712
        failed = failed.sort_values("ts", ascending=False).head(20)

        if not failed.empty:
            for _, r in failed.iterrows():
                st.error(f"{r['email']} — {r['ts'].strftime('%Y-%m-%d %H:%M UTC')}")
        else:
            st.success("No failed logins found in recent auth logs.")
    else:
        st.info(
            "No `auth_logs` data yet. Optional: log failed and successful logins "
            "into `auth_logs` (ts, email, success)."
        )

    st.markdown("---")

    # ---- Administrative Action Log (audit trail) ----
    st.subheader("🧾 Administrative Action Log")

    admin_events = []
    try:
        admin_events = list(admin_logs_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(25))
    except Exception:
        admin_events = []

    if admin_events:
        for ev in admin_events:
            ts = ev.get("timestamp")
            actor = ev.get("actor_email", "—")
            action = ev.get("action", "—")
            target = ev.get("target", "—")
            meta = ev.get("meta", {})

            with st.expander(f"{fmt_dt(ts)}  •  {action}  •  {actor}"):
                st.write(f"**Actor:** `{actor}`")
                st.write(f"**Target:** `{target}`")
                if isinstance(meta, dict) and meta:
                    st.write("**Meta:**")
                    st.json(meta)
    else:
        st.info("No admin logs found yet. Once admin actions occur, they will appear here.")
