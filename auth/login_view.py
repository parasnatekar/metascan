import streamlit as st
from auth.auth_utils import authenticate_user

def show_login():
    st.subheader("🔐 Login to MetaScan")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        success, user = authenticate_user(email, password)

        if success:
            st.session_state.logged_in = True
            st.session_state.user = {
                "username": user["username"],
                "email": user["email"],
                "role": user["role"]
            }
            st.success("✅ Logged in successfully")
            st.rerun()
        else:
            st.error("❌ Invalid email or password")
