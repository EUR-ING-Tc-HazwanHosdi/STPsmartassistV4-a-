import streamlit as st
import numpy as np
import pandas as pd
import cv2
from PIL import Image
from datetime import datetime
import bcrypt
import stripe
from sqlalchemy import create_engine

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="STP Smart Assist SaaS", layout="wide")

# =========================================================
# STRIPE CONFIG (FILL THIS)
# =========================================================
stripe.api_key = "YOUR_STRIPE_SECRET_KEY"
PRICE_ID = "YOUR_PRICE_ID"

def create_checkout_session(email):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=email,
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        success_url="https://your-app.streamlit.app/",
        cancel_url="https://your-app.streamlit.app/"
    )
    return session.url

# =========================================================
# POSTGRESQL CONFIG (FILL THIS)
# =========================================================
DATABASE_URL = "postgresql://user:password@host:5432/dbname"
engine = create_engine(DATABASE_URL)

# =========================================================
# DATABASE FUNCTIONS
# =========================================================
def save_history_db(user, data, result):
    try:
        with engine.begin() as conn:
            conn.execute("""
                INSERT INTO history (username, sv30, do, mlss, nh3, svi, time)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                user,
                data["SV30"],
                data["DO"],
                data["MLSS"],
                data["NH3"],
                result["SVI"],
                datetime.now()
            ))
    except:
        pass  # fallback safe mode

# =========================================================
# USER SYSTEM (SAFER DEMO MODE)
# =========================================================
USERS = {
    "demo": {
        "password": bcrypt.hashpw("1234".encode(), bcrypt.gensalt()),
        "plan": "basic",
        "name": "Demo User"
    },
    "plant1": {
        "password": bcrypt.hashpw("1234".encode(), bcrypt.gensalt()),
        "plan": "premium",
        "name": "Plant Operator"
    }
}

def authenticate(username, password):
    user = USERS.get(username)
    if user and bcrypt.checkpw(password.encode(), user["password"]):
        return {"status": True, "plan": user["plan"], "name": user["name"]}
    return {"status": False}

# =========================================================
# SESSION
# =========================================================
if "user" not in st.session_state:
    st.session_state.user = None

# LOGIN PAGE
if st.session_state.user is None:
    st.title("🔐 STP Smart Assist SaaS")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        res = authenticate(username, password)
        if res["status"]:
            st.session_state.user = res
            st.rerun()
        else:
            st.error("Invalid login")

    st.stop()

user = st.session_state.user

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title(f"👤 {user['name']}")
st.sidebar.write(f"Plan: {user['plan']}")

if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

# =========================================================
# STRIPE UPGRADE BUTTON
# =========================================================
if user["plan"] != "premium":
    if st.sidebar.button("💳 Upgrade to Premium"):
        url = create_checkout_session(user["name"])
        st.sidebar.markdown(f"[Pay Here]({url})")

# =========================================================
# ENGINE (STP LOGIC)
# =========================================================
def process_engine(data):
    findings, actions = [], []

    svi = data["SV30"] / data["MLSS"] * 1000 if data["MLSS"] > 0 else 0

    if data["DO"] < 1.5:
        findings.append("Low DO")
        actions.append("Increase aeration")

    if svi > 150:
        findings.append("Bulking Sludge")
        actions.append("Check filaments")

    if data["NH3"] > 10:
        findings.append("High Ammonia")
        actions.append("Increase nitrification")

    if not findings:
        findings.append("System Stable")
        actions.append("Maintain operation")

    return {"findings": findings, "actions": actions, "SVI": round(svi, 2)}

# =========================================================
# IMAGE ENGINE (PREMIUM)
# =========================================================
def image_engine(img):
    image = np.array(img)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    foam = np.sum(edges > 0) / edges.size
    brightness = np.mean(gray)

    if foam > 0.15:
        return "Foaming Sludge" if brightness > 180 else "Brown Foam"
    return "Normal"

# =========================================================
# INPUTS
# =========================================================
st.title("🌊 STP Smart Assist SaaS Platform")

data = {
    "SV30": st.sidebar.number_input("SV30", 250),
    "DO": st.sidebar.number_input("DO", 2.0),
    "MLSS": st.sidebar.number_input("MLSS", 3000),
    "NH3": st.sidebar.number_input("NH3", 5.0)
}

# =========================================================
# MAIN DASHBOARD
# =========================================================
col1, col2 = st.columns(2)

# IMAGE MODULE
with col1:
    st.subheader("📸 Visual AI")

    if user["plan"] == "premium":
        file = st.file_uploader("Upload Image")

        if file:
            img = Image.open(file)
            st.image(img)
            st.success(image_engine(img))
    else:
        st.warning("Premium feature locked")

# PROCESS MODULE
with col2:
    st.subheader("📊 Process Engine")

    result = process_engine(data)

    st.write(result["findings"])
    st.write(result["actions"])
    st.metric("SVI", result["SVI"])

# =========================================================
# SAVE + TREND SYSTEM
# =========================================================
if st.button("💾 Save Data"):
    save_history_db(user["name"], data, result)
    st.success("Saved to DB (or fallback)")

# =========================================================
# PREMIUM PDF / STRIPE FLOW READY
# =========================================================
if user["plan"] == "premium":
    st.info("Premium user access enabled")
else:
    st.info("Upgrade to unlock AI reports + export + advanced analytics")
