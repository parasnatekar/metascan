import streamlit as st
from bson import ObjectId
import gridfs
from admin.logger import log_admin
from db import db, collection

users_col = db["users"]
fs = gridfs.GridFS(db)


def delete_pdf_from_gridfs(file_id):
    if not file_id:
        return
    try:
        if not isinstance(file_id, ObjectId):
            file_id = ObjectId(str(file_id))
        fs.delete(file_id)
    except Exception as e:
        print(f"GridFS delete failed: {e}")


def cascade_delete_user(user_email):
    docs = list(collection.find({"uploaded_by": user_email}))
    deleted_files = 0
    for doc in docs:
        if doc.get("file_id"):
            delete_pdf_from_gridfs(doc["file_id"])
            deleted_files += 1
    deleted_papers = len(docs)
    collection.delete_many({"uploaded_by": user_email})
    doc_ids = [doc["_id"] for doc in docs]
    if doc_ids:
        users_col.update_many({}, {"$pull": {"bookmarks": {"$in": doc_ids}}})
    users_col.delete_one({"email": user_email})
    return {"deleted_papers": deleted_papers, "deleted_files": deleted_files}


def show_user_management():

    # ── Page styles (scoped) ──
    st.markdown("""
    <style>
    .um-header {
        padding: 28px 0 20px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 28px;
    }
    .um-breadcrumb {
        font-family: 'Space Mono', monospace;
        font-size: 10px;
        color: #FF6B35;
        letter-spacing: 3px;
        margin-bottom: 8px;
    }
    .um-title {
        font-family: 'Syne', sans-serif;
        font-size: 32px;
        font-weight: 800;
        color: #E8EDF2;
        letter-spacing: -0.5px;
    }
    .um-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 14px;
        color: #5A6472;
        margin-top: 6px;
    }
    .um-stat {
        background: #0D1117;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 18px 20px;
        text-align: center;
    }
    .um-stat-val {
        font-family: 'Space Mono', monospace;
        font-size: 28px;
        font-weight: 700;
        line-height: 1;
    }
    .um-stat-label {
        font-family: 'Space Mono', monospace;
        font-size: 10px;
        color: #5A6472;
        letter-spacing: 1px;
        margin-top: 6px;
    }
    .um-card {
        background: #0D1117;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }
    .um-card:hover { border-color: rgba(255,107,53,0.25); }
    .um-username {
        font-family: 'Syne', sans-serif;
        font-size: 16px;
        font-weight: 700;
        color: #E8EDF2;
    }
    .um-email {
        font-family: 'Space Mono', monospace;
        font-size: 11px;
        color: #5A6472;
        margin-top: 2px;
    }
    .um-role-admin {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-family: 'Space Mono', monospace;
        font-size: 10px;
        letter-spacing: 1px;
        background: rgba(255,107,53,0.1);
        border: 1px solid rgba(255,107,53,0.3);
        color: #FF6B35;
    }
    .um-role-user {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-family: 'Space Mono', monospace;
        font-size: 10px;
        letter-spacing: 1px;
        background: rgba(0,255,148,0.08);
        border: 1px solid rgba(0,255,148,0.2);
        color: #00FF94;
    }
    .um-you {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-family: 'Space Mono', monospace;
        font-size: 9px;
        letter-spacing: 1px;
        background: rgba(0,224,255,0.08);
        border: 1px solid rgba(0,224,255,0.15);
        color: #00E0FF;
        margin-left: 8px;
        vertical-align: middle;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ──
    st.markdown("""
    <div class="um-header">
        <div class="um-breadcrumb">METASCAN // ADMIN // USER MANAGEMENT</div>
        <div class="um-title">User Management</div>
        <div class="um-subtitle">Manage accounts, roles, and cascade-delete users with their content</div>
    </div>
    """, unsafe_allow_html=True)

    current_admin_email = st.session_state.user["email"]

    # ── Stats ──
    all_users = list(users_col.find({}, {"password": 0}))
    total_users = len(all_users)
    total_admins = sum(1 for u in all_users if u.get("role") == "admin")
    total_normal = total_users - total_admins
    total_papers = collection.count_documents({})

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="um-stat">
            <div class="um-stat-val" style="color:#00E0FF;">{total_users}</div>
            <div class="um-stat-label">TOTAL USERS</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="um-stat">
            <div class="um-stat-val" style="color:#FF6B35;">{total_admins}</div>
            <div class="um-stat-label">ADMINS</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="um-stat">
            <div class="um-stat-val" style="color:#00FF94;">{total_normal}</div>
            <div class="um-stat-label">REGULAR USERS</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="um-stat">
            <div class="um-stat-val" style="color:#A78BFA;">{total_papers}</div>
            <div class="um-stat-label">TOTAL PAPERS</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Filters ──
    st.markdown("""<div style="font-family:'Space Mono',monospace; font-size:10px;
        color:#5A6472; letter-spacing:2px; margin-bottom:10px;">FILTER USERS</div>""",
        unsafe_allow_html=True)

    f1, f2 = st.columns([3, 1])
    with f1:
        query = st.text_input("", placeholder="Search by username or email...", label_visibility="collapsed")
    with f2:
        role_filter = st.selectbox("", ["all", "admin", "user"], label_visibility="collapsed")

    # Apply filters
    filtered = []
    q = (query or "").strip().lower()
    for u in all_users:
        role = u.get("role", "user")
        if role_filter != "all" and role != role_filter:
            continue
        if q and q not in u.get("username", "").lower() and q not in u.get("email", "").lower():
            continue
        filtered.append(u)

    st.markdown(f"""<div style="font-family:'Space Mono',monospace; font-size:10px;
        color:#5A6472; letter-spacing:2px; margin: 16px 0 12px;">
        {len(filtered)} USER{'S' if len(filtered) != 1 else ''} FOUND
    </div>""", unsafe_allow_html=True)

    if not filtered:
        st.markdown("""<div style="text-align:center; padding:48px; color:#5A6472;
            font-family:'Space Mono',monospace; font-size:12px;
            border:1px dashed rgba(255,255,255,0.06); border-radius:10px;">
            NO USERS MATCH YOUR FILTERS
        </div>""", unsafe_allow_html=True)
        return

    # ── User Cards ──
    for u in filtered:
        role  = u.get("role", "user")
        email = u.get("email", "")
        username = u.get("username", "Unknown")
        is_self = email == current_admin_email
        you_badge = '<span class="um-you">YOU</span>' if is_self else ""
        role_badge = f'<span class="um-role-admin">ADMIN</span>' if role == "admin" else f'<span class="um-role-user">USER</span>'

        # paper count for this user
        paper_count = collection.count_documents({"uploaded_by": email})
        joined = u.get("created_at")
        joined_str = joined.strftime("%b %d, %Y") if joined else "—"

        st.markdown(f"""
        <div class="um-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
                <div>
                    <div class="um-username">{username}{you_badge}</div>
                    <div class="um-email">{email}</div>
                    <div style="margin-top:8px; display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                        {role_badge}
                        <span style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472;">
                            📄 {paper_count} paper{'s' if paper_count != 1 else ''}
                        </span>
                        <span style="font-family:'Space Mono',monospace; font-size:10px; color:#5A6472;">
                            🗓 Joined {joined_str}
                        </span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Action buttons in columns below card
        if not is_self:
            btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2])

            with btn_col1:
                if role == "admin":
                    if st.button("⬇️ Demote", key=f"demote_{u['_id']}", use_container_width=True):
                        users_col.update_one({"_id": ObjectId(u["_id"])}, {"$set": {"role": "user"}})
                        log_admin(current_admin_email, "demote_user", email,
                                  {"from_role": "admin", "to_role": "user"})
                        st.success(f"{username} demoted to user.")
                        st.rerun()
                else:
                    if st.button("⬆️ Promote", key=f"promote_{u['_id']}", use_container_width=True):
                        users_col.update_one({"_id": ObjectId(u["_id"])}, {"$set": {"role": "admin"}})
                        log_admin(current_admin_email, "promote_user", email,
                                  {"from_role": "user", "to_role": "admin"})
                        st.success(f"{username} promoted to admin.")
                        st.rerun()

            with btn_col2:
                confirm = st.checkbox("Confirm", key=f"confirm_del_{u['_id']}")

            with btn_col3:
                if st.button(
                    f"🗑️ Delete {username} + {paper_count} paper{'s' if paper_count != 1 else ''}",
                    key=f"delete_{u['_id']}",
                    disabled=not confirm,
                    use_container_width=True
                ):
                    result = cascade_delete_user(email)
                    log_admin(current_admin_email, "delete_user_cascade", email, {
                        "deleted_papers": result.get("deleted_papers", 0),
                        "deleted_files": result.get("deleted_files", 0)
                    })
                    st.success(f"✅ {username} and all their data deleted.")
                    st.rerun()

        else:
            st.markdown("""<div style="font-family:'Space Mono',monospace; font-size:10px;
                color:#5A6472; padding: 0 0 8px 2px; letter-spacing:1px;">
                🛑 CANNOT MODIFY YOUR OWN ACCOUNT
            </div>""", unsafe_allow_html=True)

        st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)