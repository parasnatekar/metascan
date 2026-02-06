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

    # delete PDFs from GridFS
    deleted_files = 0
    for doc in docs:
        if doc.get("file_id"):
            delete_pdf_from_gridfs(doc["file_id"])
            deleted_files += 1

    # delete papers
    deleted_papers = len(docs)
    collection.delete_many({"uploaded_by": user_email})

    # remove bookmarks referencing deleted papers
    doc_ids = [doc["_id"] for doc in docs]
    if doc_ids:
        users_col.update_many({}, {"$pull": {"bookmarks": {"$in": doc_ids}}})

    # delete user
    users_col.delete_one({"email": user_email})

    return {
        "deleted_papers": deleted_papers,
        "deleted_files": deleted_files
    }


def show_user_management():
    st.title("👥 User Management")
    st.caption("Manage users, roles, and cleanly delete accounts with their uploaded content.")

    current_admin_email = st.session_state.user["email"]

    # top metrics
    all_users = list(users_col.find({}, {"password": 0}))
    total_users = len(all_users)
    total_admins = sum(1 for u in all_users if u.get("role") == "admin")
    total_normal = total_users - total_admins

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Users", total_users)
    m2.metric("Admins", total_admins)
    m3.metric("Users", total_normal)

    st.divider()

    # filters
    f1, f2 = st.columns([2, 1])
    with f1:
        query = st.text_input("Search by username/email", placeholder="e.g. paras or abc@gmail.com")
    with f2:
        role_filter = st.selectbox("Filter role", ["all", "admin", "user"])

    # apply filters
    filtered = []
    q = (query or "").strip().lower()
    for u in all_users:
        role = u.get("role", "user")
        if role_filter != "all" and role != role_filter:
            continue
        if q and (q not in (u.get("username", "").lower()) and q not in (u.get("email", "").lower())):
            continue
        filtered.append(u)

    if not filtered:
        st.info("No users match the current filters.")
        return

    # user cards
    for u in filtered:
        role = u.get("role", "user")
        email = u.get("email", "")
        username = u.get("username", "Unknown")

        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 3])

            with c1:
                st.markdown(f"### {username}")
                st.caption(email)

            with c2:
                if role == "admin":
                    st.markdown("**Role:** 🔐 `admin`")
                else:
                    st.markdown("**Role:** 👤 `user`")

            with c3:
                # ---- promote/demote ----
                if role == "admin":
                    if email == current_admin_email:
                        st.caption("🛑 You cannot demote yourself")
                    else:
                        if st.button("⬇️ Demote to user", key=f"demote_{u['_id']}"):
                            users_col.update_one(
                                {"_id": ObjectId(u["_id"])},
                                {"$set": {"role": "user"}}
                            )

                            # ✅ LOG ADMIN ACTION
                            log_admin(
                                actor_email=current_admin_email,
                                action="demote_user",
                                target=email,
                                meta={"from_role": "admin", "to_role": "user"}
                            )

                            st.success("User demoted")
                            st.rerun()
                else:
                    if st.button("⬆️ Promote to admin", key=f"promote_{u['_id']}"):
                        users_col.update_one(
                            {"_id": ObjectId(u["_id"])},
                            {"$set": {"role": "admin"}}
                        )

                        # ✅ LOG ADMIN ACTION
                        log_admin(
                            actor_email=current_admin_email,
                            action="promote_user",
                            target=email,
                            meta={"from_role": "user", "to_role": "admin"}
                        )

                        st.success("User promoted")
                        st.rerun()

                # ---- delete user (cascade) ----
                if email == current_admin_email:
                    st.caption("🛑 You cannot delete yourself")
                else:
                    confirm = st.checkbox("Confirm delete", key=f"confirm_del_{u['_id']}")
                    if st.button("🗑️ Delete user + their papers", key=f"delete_{u['_id']}", disabled=not confirm):
                        result = cascade_delete_user(email)

                        # ✅ LOG ADMIN ACTION
                        log_admin(
                            actor_email=current_admin_email,
                            action="delete_user_cascade",
                            target=email,
                            meta={
                                "deleted_papers": result.get("deleted_papers", 0),
                                "deleted_files": result.get("deleted_files", 0)
                            }
                        )

                        st.success("User and all associated data deleted")
                        st.rerun()
