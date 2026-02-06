import streamlit as st
from datetime import datetime, timezone, timedelta

from auth.login_view import (
    users_collection,
    pending_users_col,
    is_valid_email,
    hash_password,
    create_verify_code,
    send_verification_code_email,
    OTP_TTL_MINUTES,
    OTP_MAX_ATTEMPTS,
)


def render_register_tab():
    st.subheader("🧾 Register (OTP Verification)")
    st.caption("We will send a 6-digit code to your email. Enter it below to activate your account.")

    username = st.text_input("Username", key="reg_username")
    reg_email = st.text_input("Register Email", key="reg_email")
    reg_password = st.text_input("Register Password", type="password", key="reg_password")
    confirm = st.text_input("Confirm Password", type="password", key="reg_confirm")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("📩 Send Verification Code", key="send_otp_btn", use_container_width="stretch"):
            reg_email_clean = (reg_email or "").strip().lower()

            if not is_valid_email(reg_email_clean):
                st.error("❌ Please enter a valid email format.")
            elif reg_password != confirm:
                st.error("❌ Passwords do not match.")
            elif users_collection.find_one({"email": reg_email_clean}):
                st.error("❌ User already exists.")
            else:
                # clean old pending entries
                pending_users_col.delete_many({"email": reg_email_clean})

                code = create_verify_code()
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)

                pending_users_col.insert_one({
                    "username": (username or "").strip() or "user",
                    "email": reg_email_clean,
                    "password_hash": hash_password(reg_password),
                    "code": code,
                    "expires_at": expires_at,
                    "created_at": datetime.now(timezone.utc),
                    "attempts": 0,
                })

                try:
                    send_verification_code_email(reg_email_clean, code)
                    st.success("✅ OTP sent! Check inbox/spam. Expires in 15 minutes.")
                except Exception as e:
                    st.error(f"❌ Could not send email: {e}")

    st.markdown("### ✅ Verify OTP")
    otp_email = st.text_input("Email (same as registration)", key="otp_email")
    otp_code = st.text_input("6-digit code", key="otp_code", max_chars=6)

    with c2:
        if st.button("✅ Verify & Create Account", key="verify_otp_btn", use_container_width="stretch"):
            otp_email_clean = (otp_email or "").strip().lower()
            otp_code_clean = (otp_code or "").strip()

            pending = pending_users_col.find_one({"email": otp_email_clean})
            if not pending:
                st.error("❌ No pending registration for this email. Please send OTP again.")
                st.stop()

            exp = pending.get("expires_at")
            if exp and isinstance(exp, datetime) and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)

            if exp and datetime.now(timezone.utc) > exp:
                pending_users_col.delete_one({"_id": pending["_id"]})
                st.error("⏳ OTP expired. Please send a new OTP.")
                st.stop()

            attempts = int(pending.get("attempts", 0))
            if attempts >= OTP_MAX_ATTEMPTS:
                st.error("⛔ Too many wrong attempts. Please resend OTP.")
                st.stop()

            if otp_code_clean != str(pending.get("code", "")):
                pending_users_col.update_one({"_id": pending["_id"]}, {"$inc": {"attempts": 1}})
                st.error("❌ Incorrect OTP. Try again.")
                st.stop()

            # create user
            users_collection.insert_one({
                "username": pending.get("username", "user"),
                "email": pending["email"],
                "password": pending["password_hash"],
                "role": "user",
                "created_at": datetime.now(timezone.utc),
                "last_login": None,
                "bookmarks": [],
            })

            pending_users_col.delete_one({"_id": pending["_id"]})
            st.success("✅ Email verified! Account created. You can login now.")
