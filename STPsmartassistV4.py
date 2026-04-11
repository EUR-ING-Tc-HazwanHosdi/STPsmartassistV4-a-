import streamlit as st
import numpy as np
import pandas as pd
import cv2
from PIL import Image
import os
import bcrypt
from sqlalchemy import create_engine
from datetime import datetime
import os
import streamlit as st

st.write("DEBUG DATABASE_URL:", os.getenv("DATABASE_URL"))

# =========================================================
# CONFIG
# =========================================================
st.set_page_config("STP Smart Assist SaaS", layout="wide")

# =========================================================
# DATABASE (SUPABASE / POSTGRES SAFE LAYER)
# =========================================================
DATABASE_URL = os.getenv("DATABASE_URL")

engine = None
DB_OK = False

if DATABASE_URL:
    try:
        engine = create_engine(
            DATABASE_URL,
            connect_args={"sslmode": "require"},
            pool_pre_ping=True,
            pool_recycle=300
        )
        engine.connect()
        DB_OK = True
    except:
        engine = None
        DB_OK = False

# =========================================================
# SAFE DB FUNCTIONS
# =========================================================
def db_exec(query, params=()):
    if not DB_OK:
        return None
    try:
        with engine.begin() as conn:
            return conn.execute(query, params)
    except:
        return None


def db_fetchone(query, params=()):
    if not DB_OK:
        return None
    try:
        with engine.begin() as conn:
            return conn.execute(query, params).fetchone()
    except:
        return None

# =========================================================
# AUTH SYSTEM
# =========================================================
def hash_pw(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_pw(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())


def register_user(username, password, name):

    if not DB_OK:
        return {"status": False, "msg": "Database offline"}

    try:
        db_exec("""
            INSERT INTO users (username, password, name, plan)
            VALUES (%s,%s,%s,'basic')
        """, (username, hash_pw(password), name))

        return {"status": True}

    except Exception as e:
        return {"status": False, "msg": str(e)}


def authenticate(username, password):

    # fallback mode (NO DB)
    if not DB_OK:
        if username == "demo" and password == "1234":
            return {
                "status": True,
                "username": "demo",
                "name": "Demo User",
                "plan": "basic"
            }
        return {"status": False}

    user = db_fetchone("""
        SELECT username, password, name, plan
        FROM users WHERE username=%s
    """, (username,))

    if user and check_pw(password, user[1]):
        return {
            "status": True,
            "username": user[0],
            "name": user[2],
            "plan": user[3]
        }

    return {"status": False}

# =========================================================
# STP PROCESS ENGINE
# =========================================================
def process_engine(data):

    svi = data["SV30"] / data["MLSS"] * 1000 if data["MLSS"] else 0

    findings = []
    actions = []

    if data["DO"] < 1.5:
        findings.append("Low DO")
        actions.append("Increase aeration")

    if svi > 150:
        findings.append("Bulking Sludge")
        actions.append("Increase RAS")

    if data["NH3"] > 10:
        findings.append("High Ammonia")
        actions.append("Improve nitrification")

    if not findings:
        findings.append("System Stable")
        actions.append("Maintain operation")

    return {
        "SVI": round(svi, 2),
        "findings": findings,
        "actions": actions
    }

# =========================================================
# IMAGE ANALYSIS ENGINE
# =========================================================
def image_engine(img):
    img = np.array(img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    foam = np.sum(edges > 0) / edges.size

    return "Foaming Sludge" if foam > 0.15 else "Normal Condition"

# =========================================================
# SESSION
# =========================================================
if "user" not in st.session_state:
    st.session_state.user = None

# =========================================================
# AUTH UI
# =========================================================
if st.session_state.user is None:

    st.title("🌊 STP Smart Assist SaaS")

    menu = st.radio("Access", ["Login", "Register"])

    if menu == "Register":
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        n = st.text_input("Name")

        if st.button("Create Account"):
            res = register_user(u, p, n)
            if res["status"]:
                st.success("Account created")
            else:
                st.error(res["msg"])

    if menu == "Login":
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login"):
            res = authenticate(u, p)
            if res["status"]:
                st.session_state.user = res
                st.rerun()
            else:
                st.error("Invalid login")

    st.stop()

# =========================================================
# DASHBOARD
# =========================================================
user = st.session_state.user

st.sidebar.title("👤 " + user["name"])
st.sidebar.write("Plan:", user["plan"])

st.title("📊 STP Dashboard")

data = {
    "SV30": st.sidebar.number_input("SV30", 250),
    "DO": st.sidebar.number_input("DO", 2.0),
    "MLSS": st.sidebar.number_input("MLSS", 3000),
    "NH3": st.sidebar.number_input("NH3", 5.0)
}

result = process_engine(data)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Process Analysis")
    st.write(result["findings"])
    st.write(result["actions"])
    st.metric("SVI", result["SVI"])

with col2:
    st.subheader("Image AI Analysis")

    if user["plan"] in ["premium", "enterprise"]:
        file = st.file_uploader("Upload Image")
        if file:
            img = Image.open(file)
            st.image(img)
            st.success(image_engine(img))
    else:
        st.warning("Upgrade required for AI Vision")

# =========================================================
# SAVE HISTORY (OPTIONAL)
# =========================================================
if DB_OK and st.button("Save Record"):

    db_exec("""
        INSERT INTO history (username, sv30, do, mlss, nh3, svi, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (
        user["username"],
        data["SV30"],
        data["DO"],
        data["MLSS"],
        data["NH3"],
        result["SVI"],
        datetime.now()
    ))

    st.success("Saved to database")
