import streamlit as st
from auth.auth_utils import create_user

def show_register():
    st.subheader("📝 Create Account")

    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")

    if st.button("Register"):
        if password != confirm:
            st.error("❌ Passwords do not match")
            return

        success, msg = create_user(username, email, password)

        if success:
            st.success("✅ Account created. Please login.")
        else:
            st.error(msg)
