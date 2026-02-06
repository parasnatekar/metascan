import streamlit as st
import re
import bcrypt
from datetime import datetime, timezone, timedelta

# NEW: email verification + google login helpers
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from db import db
from admin.logger import log_auth


# ================= AUTH SETUP =================
users_collection = db["users"]
pending_users_col = db["pending_users"]  # pending until email verified

EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
OTP_TTL_MINUTES = 15
OTP_MAX_ATTEMPTS = 5


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    return re.match(EMAIL_REGEX, email.strip()) is not None


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())


def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)


# ✅ OTP-based verification (works local + cloud + phone)
def create_verify_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def send_verification_code_email(to_email: str, code: str):
    """
    Uses SMTP settings from st.secrets:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    """
    msg = EmailMessage()
    msg["Subject"] = "Verify your MetaScan account (OTP)"
    msg["From"] = st.secrets["SMTP_USER"]
    msg["To"] = to_email
    msg.set_content(
        "Your MetaScan verification code is:\n\n"
        f"{code}\n\n"
        f"This code expires in {OTP_TTL_MINUTES} minutes.\n"
        "If you didn't request this, ignore this email."
    )

    with smtplib.SMTP_SSL(st.secrets["SMTP_HOST"], int(st.secrets["SMTP_PORT"])) as smtp:
        smtp.login(st.secrets["SMTP_USER"], st.secrets["SMTP_PASS"])
        smtp.send_message(msg)


def google_redirect_uri() -> str:
    """
    Google requires redirect_uri to match exactly what you registered.
    Set in secrets.toml:
      GOOGLE_REDIRECT_URI = "http://localhost:8501/"
      OR your deployed url with trailing slash.
    """
    v = str(st.secrets.get("GOOGLE_REDIRECT_URI", "")).strip()
    if not v:
        # fallback for local dev
        return "http://localhost:8501/"
    return v


def google_auth_url():
    base = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": st.secrets["GOOGLE_CLIENT_ID"],
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return base + "?" + urlencode(params)


def google_exchange_code_for_tokens(code: str):
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": st.secrets["GOOGLE_CLIENT_ID"],
        "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": google_redirect_uri(),
    }
    r = requests.post(token_url, data=data, timeout=20)
    r.raise_for_status()
    return r.json()


def render_auth_page():
    # Session defaults
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user" not in st.session_state:
        st.session_state.user = None

    # ================= LOGIN / REGISTER UI =================
    if not st.session_state.logged_in:

        # ---------- WOW UI ----------
        st.markdown(
            """
        <style>
        .stApp {
          background: radial-gradient(1200px 600px at 20% 0%, rgba(56,189,248,0.18), transparent 60%),
                      radial-gradient(900px 500px at 80% 20%, rgba(34,197,94,0.14), transparent 55%),
                      linear-gradient(135deg, #0B0F17, #0E1117 55%, #0B0F17);
          color: #E5E7EB;
        }
        .auth-wrap {
          max-width: 980px;
          margin: 0 auto;
          padding: 18px 0 0;
        }
        .auth-hero {
          border-radius: 22px;
          padding: 26px 28px;
          border: 1px solid rgba(255,255,255,0.10);
          background: rgba(15, 23, 42, 0.50);
          backdrop-filter: blur(14px);
          box-shadow: 0 28px 80px rgba(0,0,0,0.55);
        }
        .auth-title {
          font-size: 42px;
          font-weight: 900;
          margin: 0;
          letter-spacing: -0.5px;
          background: linear-gradient(90deg, #38BDF8, #22C55E);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        .auth-subtitle {
          margin-top: 8px;
          color: rgba(229,231,235,0.75);
          font-size: 15px;
          line-height: 1.6;
        }
        .badges {
          display:flex; gap:10px; flex-wrap:wrap;
          margin-top: 10px;
        }
        .badge {
          font-size: 12px;
          color: rgba(229,231,235,0.75);
          border: 1px solid rgba(255,255,255,0.10);
          background: rgba(17,24,39,0.45);
          padding: 6px 10px;
          border-radius: 999px;
        }
        .stTabs [data-baseweb="tab-list"] {
          gap: 12px;
          margin-top: 14px;
        }
        div[data-baseweb="input"] input {
          background: rgba(17, 24, 39, 0.65) !important;
          border: 1px solid rgba(255,255,255,0.10) !important;
        }
        .stButton button {
          border-radius: 14px !important;
          padding: 10px 16px !important;
          border: 1px solid rgba(255,255,255,0.12) !important;
          background: linear-gradient(135deg, rgba(56,189,248,0.20), rgba(34,197,94,0.15)) !important;
          box-shadow: 0 14px 30px rgba(0,0,0,0.35) !important;
          transition: transform .12s ease, box-shadow .12s ease;
        }
        .stButton button:hover {
          transform: translateY(-1px);
          box-shadow: 0 18px 44px rgba(0,0,0,0.45) !important;
        }
        </style>
        """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div class="auth-wrap">
          <div class="auth-hero">
            <div class="auth-title">🔐 MetaScan Authentication</div>
            <div class="auth-subtitle">
              Login to access your research workspace. Admin access is restricted.<br>
              Registration requires email verification.
              <div class="badges">
                <span class="badge">✅ Email verification (OTP)</span>
                <span class="badge">🔵 Google Login</span>
                <span class="badge">🛡️ Audit logs</span>
                <span class="badge">⏱️ Perf logs</span>
              </div>
            </div>
          </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.write("")

        # ---------- GOOGLE OAUTH CALLBACK HANDLER ----------
        params = st.query_params
        code = params.get("code")
        if code:
            code_str = code[0] if isinstance(code, (list, tuple)) else str(code)

            try:
                tokens = google_exchange_code_for_tokens(str(code_str))
                idt = tokens.get("id_token")
                if not idt:
                    raise Exception("Missing id_token from Google")

                info = id_token.verify_oauth2_token(
                    idt,
                    grequests.Request(),
                    st.secrets["GOOGLE_CLIENT_ID"],
                )

                email = (info.get("email") or "").strip().lower()
                name = (info.get("name") or "Google User").strip()

                if not email:
                    raise Exception("Google did not return an email")

                user = users_collection.find_one({"email": email})
                if not user:
                    users_collection.insert_one(
                        {
                            "username": name,
                            "email": email,
                            "password": None,
                            "role": "user",
                            "created_at": datetime.now(timezone.utc),
                            "last_login": datetime.now(timezone.utc),
                            "bookmarks": [],
                        }
                    )
                    role = "user"
                else:
                    role = user.get("role", "user")
                    users_collection.update_one(
                        {"email": email},
                        {"$set": {"last_login": datetime.now(timezone.utc)}},
                    )

                log_auth(email, True, role=role, reason="google_login_ok")

                st.session_state.logged_in = True
                st.session_state.user = {
                    "username": name if name else (user.get("username") if user else "user"),
                    "email": email,
                    "role": role,
                }

                st.query_params.clear()
                st.success("✅ Logged in with Google")
                st.rerun()

            except Exception as e:
                st.query_params.clear()
                st.error(f"❌ Google login failed: {e}")
                st.stop()

        tab1, tab2, tab3 = st.tabs(["User Login", "Register", "Admin Login"])

        # ---------------- USER LOGIN ----------------
        with tab1:
            st.link_button("🔵 Continue with Google", google_auth_url(), use_container_width="stretch")
            st.write("— or —")

            email = st.text_input("Email", key="user_email")
            password = st.text_input("Password", type="password", key="user_password")

            if st.button("Login", key="user_login_btn"):
                email_clean = (email or "").strip().lower()
                user = users_collection.find_one({"email": email_clean})

                if user and user.get("password") is None:
                    log_auth(email_clean, False, reason="google_account_use_google_login")
                    st.error("🔵 This account uses Google Login. Please use **Continue with Google**.")
                    st.stop()

                if not user or not user.get("password") or not verify_password(password, user["password"]):
                    log_auth(email_clean, False, reason="invalid_credentials")
                    st.error("❌ Invalid credentials")
                else:
                    role = user.get("role", "user")

                    if role == "admin":
                        log_auth(email_clean, False, role="admin", reason="admin_used_user_login")
                        st.error("🛡️ Admin account detected. Please login using the **Admin Login** tab.")
                    else:
                        log_auth(email_clean, True, role=role, reason="user_login_ok")
                        users_collection.update_one(
                            {"email": user["email"]},
                            {"$set": {"last_login": datetime.now(timezone.utc)}},
                        )

                        st.session_state.logged_in = True
                        st.session_state.user = {
                            "username": user.get("username", "user"),
                            "email": user["email"],
                            "role": role,
                        }
                        st.success("✅ Login successful")
                        st.rerun()

        # ---------------- REGISTER (OTP EMAIL VERIFICATION) ----------------
        with tab2:
            from auth import register_view
            register_view.render_register_tab()

        # ---------------- ADMIN LOGIN ----------------
        with tab3:
            st.subheader("🛡️ Admin Login")
            st.caption("Only administrators can login here. No new accounts can be created.")

            admin_email = st.text_input("Admin Email", key="admin_email")
            admin_password = st.text_input("Admin Password", type="password", key="admin_password")

            if st.button("Admin Login", key="admin_login_btn"):
                admin_email_clean = (admin_email or "").strip().lower()
                user = users_collection.find_one({"email": admin_email_clean})

                if user and user.get("password") is None:
                    log_auth(admin_email_clean, False, reason="google_account_admin_login_blocked")
                    st.error("🔵 This account uses Google Login. Use Google login or set a local password.")
                    st.stop()

                if not user or not user.get("password") or not verify_password(admin_password, user["password"]):
                    log_auth(admin_email_clean, False, reason="invalid_admin_credentials")
                    st.error("❌ Invalid admin credentials")
                else:
                    role = user.get("role", "user")

                    if role != "admin":
                        log_auth(admin_email_clean, False, role=role, reason="non_admin_blocked_admin_portal")
                        st.error("⛔ Access denied. Admins only.")
                    else:
                        log_auth(admin_email_clean, True, role="admin", reason="admin_login_ok")

                        users_collection.update_one(
                            {"email": user["email"]},
                            {"$set": {"last_login": datetime.now(timezone.utc)}},
                        )

                        st.session_state.logged_in = True
                        st.session_state.user = {
                            "username": user.get("username", "admin"),
                            "email": user["email"],
                            "role": role,
                        }
                        st.success("✅ Admin login successful")
                        st.rerun()

        st.stop()
