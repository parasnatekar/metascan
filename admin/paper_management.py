import streamlit as st
from bson import ObjectId
import gridfs
from datetime import datetime, timezone

from db import db, collection
from admin.logger import log_admin

users_col = db["users"]
fs = gridfs.GridFS(db)


def _safe_objectid(x):
    try:
        if isinstance(x, ObjectId):
            return x
        return ObjectId(str(x))
    except Exception:
        return None


def delete_pdf_from_gridfs(file_id):
    """Local GridFS delete to avoid import issues."""
    if not file_id:
        return False
    try:
        oid = _safe_objectid(file_id)
        if not oid:
            return False
        fs.delete(oid)
        return True
    except Exception as e:
        print(f"GridFS delete failed: {e}")
        return False


def delete_paper_cascade(paper_doc):
    """
    Deletes:
    1) PDF from GridFS (if file_id exists)
    2) Paper from documents collection
    3) Removes that paper_id from all users' bookmarks
    """
    pid = paper_doc.get("_id")
    file_id = paper_doc.get("file_id")

    deleted_file = False
    if file_id:
        deleted_file = delete_pdf_from_gridfs(file_id)

    # delete paper
    collection.delete_one({"_id": pid})

    # remove bookmarks that reference this paper
    users_col.update_many({}, {"$pull": {"bookmarks": pid}})

    return deleted_file


# ---------------- ORPHAN HELPERS ----------------
def _get_referenced_file_ids():
    """All file_ids that are referenced by paper documents."""
    ids = set()
    for d in collection.find({"file_id": {"$exists": True, "$ne": None}}, {"file_id": 1}):
        oid = _safe_objectid(d.get("file_id"))
        if oid:
            ids.add(oid)
    return ids


def _get_all_gridfs_file_ids(sample_limit=None):
    """All GridFS file _ids from fs.files (optionally sampled by limit)."""
    cur = db["fs.files"].find({}, {"_id": 1})
    if sample_limit:
        cur = cur.limit(int(sample_limit))
    return {f["_id"] for f in cur}


def _find_orphaned_file_ids(sample_limit=5000):
    """
    Orphans = GridFS files that are NOT referenced by any paper document.
    Returns: (orphans_list, scanned_total, referenced_total)
    """
    referenced = _get_referenced_file_ids()
    all_fs = _get_all_gridfs_file_ids(sample_limit=sample_limit)
    orphans = list(all_fs - referenced)
    return orphans, len(all_fs), len(referenced)


def _delete_orphans(orphan_ids):
    deleted = 0
    for fid in orphan_ids:
        try:
            fs.delete(fid)
            deleted += 1
        except Exception:
            pass
    return deleted


def show_paper_management():
    st.title("🗂️ Paper Management")
    st.caption("Admin-only controls to review and delete papers safely (with GridFS cleanup + bookmark cleanup).")

    current_admin_email = st.session_state.user["email"]

    # ---------- TOP METRICS ----------
    total_papers = collection.count_documents({})
    total_with_pdf = collection.count_documents({"file_id": {"$exists": True, "$ne": None}})
    gridfs_files = db["fs.files"].count_documents({})

    # Correct orphan estimate (GridFS files not referenced by papers)
    estimated_orphans = max(gridfs_files - total_with_pdf, 0)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Papers", total_papers)
    m2.metric("Papers with PDF", total_with_pdf)
    m3.metric("GridFS Files", gridfs_files)

    # Optional: quick hint (not a metric to keep UI clean)
    if estimated_orphans > 0:
        st.caption(f"🧹 Estimated orphaned GridFS files: **{estimated_orphans}** (use cleanup below)")

    st.divider()

    # ---------- ORPHAN CLEANUP UI (MERGED) ----------
    st.markdown("### 🧹 Orphaned PDFs (GridFS Cleanup)")
    st.caption("Orphaned = files in GridFS that are not referenced by any paper document (wastes storage).")

    with st.expander("Scan & cleanup orphaned PDFs", expanded=False):
        sample_limit = st.number_input(
            "Scan limit (fs.files sample)",
            min_value=500,
            max_value=50000,
            value=5000,
            step=500
        )

        if st.button("🔎 Scan orphans", use_container_width=True):
            orphans, scanned_total, referenced_total = _find_orphaned_file_ids(sample_limit=sample_limit)
            st.session_state["_orphans_cache"] = orphans
            st.success(
                f"Scanned {scanned_total} GridFS files. "
                f"Found {len(orphans)} orphaned files. "
                f"(Referenced by papers: {referenced_total})"
            )

        orphans_cached = st.session_state.get("_orphans_cache", [])

        if orphans_cached:
            st.warning(f"⚠️ Orphans ready to delete: {len(orphans_cached)}")

            show_ids = st.checkbox("Show sample orphan file IDs")
            if show_ids:
                st.write([str(x) for x in orphans_cached[:25]])

            confirm = st.checkbox("I understand this will permanently delete orphaned PDFs from GridFS.")
            if st.button(
                "🗑️ Delete ALL orphaned PDFs",
                type="primary",
                use_container_width=True,
                disabled=not confirm
            ):
                deleted = _delete_orphans(orphans_cached)

                # ✅ ADMIN LOG
                log_admin(
                    actor_email=current_admin_email,
                    action="delete_orphaned_gridfs_files",
                    target="gridfs",
                    meta={"deleted": deleted, "attempted": len(orphans_cached)}
                )

                st.success(f"✅ Deleted {deleted} orphaned PDFs from GridFS.")
                st.session_state["_orphans_cache"] = []
                st.rerun()
        else:
            st.info("No cached orphan scan yet. Click **Scan orphans** to detect.")

    st.divider()

    # ---------- FILTERS ----------
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])

    with f1:
        q = st.text_input("Search (title / DOI / uploader)", placeholder="e.g. pneumonia, 10.1234/xyz, abc@gmail.com")
    with f2:
        category = st.text_input("Category", placeholder="optional")
    with f3:
        only_pdf = st.selectbox("PDF", ["all", "has_pdf", "no_pdf"])
    with f4:
        sort = st.selectbox("Sort", ["Newest", "Oldest", "Title A-Z"])

    query = {}
    q = (q or "").strip()

    if q:
        # title regex OR doi exact-ish OR uploaded_by match
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"doi": {"$regex": q, "$options": "i"}},
            {"uploaded_by": {"$regex": q, "$options": "i"}},
        ]

    if category.strip():
        query["category"] = {"$regex": category.strip(), "$options": "i"}

    if only_pdf == "has_pdf":
        query["file_id"] = {"$exists": True, "$ne": None}

    elif only_pdf == "no_pdf":
        no_pdf_clause = {"$or": [{"file_id": {"$exists": False}}, {"file_id": None}]}

        # If query already has conditions, combine safely using $and
        if query:
            query = {"$and": [query, no_pdf_clause]}
        else:
            query = no_pdf_clause

    # sorting
    sort_spec = [("_id", -1)]
    if sort == "Oldest":
        sort_spec = [("_id", 1)]
    elif sort == "Title A-Z":
        sort_spec = [("title", 1)]

    # ---------- FETCH ----------
    docs = list(
        collection.find(query, {"abstract": 0})  # keep list fast
        .sort(sort_spec)
        .limit(200)
    )

    if not docs:
        st.info("No papers match the current filters.")
        return

    st.write(f"Showing **{len(docs)}** papers (max 200).")

    st.divider()

    # ---------- PAPER CARDS ----------
    for doc in docs:
        pid = doc.get("_id")
        title = doc.get("title", "Untitled")
        doi = doc.get("doi", "")
        year = doc.get("year", "")
        cat = doc.get("category", "Uncategorized")
        uploader = doc.get("uploaded_by", "Unknown")
        uploaded_at = doc.get("uploaded_at", None)
        has_pdf = bool(doc.get("file_id"))

        uploaded_at_str = ""
        if uploaded_at:
            try:
                # handle both naive + aware safely
                if uploaded_at.tzinfo is None:
                    uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)
                uploaded_at_str = uploaded_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                uploaded_at_str = str(uploaded_at)

        with st.container(border=True):
            c1, c2 = st.columns([4, 2])

            with c1:
                st.markdown(f"### {title}")
                st.caption(f"ID: {pid}")
                meta_line = f"**Category:** `{cat}`  |  **Year:** `{year or '—'}`"
                st.markdown(meta_line)

                if doi:
                    st.markdown(f"**DOI:** `{doi}`")

                st.markdown(f"**Uploaded by:** `{uploader}`")
                if uploaded_at_str:
                    st.caption(f"Uploaded at: {uploaded_at_str}")

            with c2:
                st.markdown(f"**PDF:** {'✅ has_pdf' if has_pdf else '❌ no_pdf'}")
                st.write("")

                confirm = st.checkbox("Confirm delete", key=f"confirm_paper_{pid}")

                if st.button("🗑️ Delete Paper", key=f"del_paper_{pid}", disabled=not confirm):
                    deleted_file = delete_paper_cascade(doc)

                    # ✅ ADMIN LOG
                    log_admin(
                        actor_email=current_admin_email,
                        action="delete_paper",
                        target=str(pid),
                        meta={
                            "title": title,
                            "uploaded_by": uploader,
                            "category": cat,
                            "doi": doi,
                            "had_file_id": bool(doc.get("file_id")),
                            "gridfs_deleted": bool(deleted_file),
                        },
                    )

                    st.success("Paper deleted (bookmarks cleaned + GridFS cleaned if needed).")
                    st.rerun()
