import streamlit as st
import os
import numpy as np
import cv2
from PIL import Image
import pandas as pd
from datetime import datetime

from sqlalchemy import create_engine, text
import bcrypt

# =========================================================
# 1. DATABASE LAYER (FIXED SUPABASE SAFE)
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

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        DB_OK = True

    except Exception as e:
        DB_OK = False
        st.error(f"DB Connection Error: {e}")
else:
    DB_OK = False


# =========================================================
# 2. AUTH SYSTEM (BCRYPT)
# =========================================================
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_user(username, password, name, plan="free"):
    if not DB_OK:
        return False

    hashed = hash_password(password)

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (username, password, name, plan)
            VALUES (:u, :p, :n, :pl)
        """), {"u": username, "p": hashed, "n": name, "pl": plan})

    return True


def get_user(username):
    if not DB_OK:
        return None

    with engine.connect() as conn:
        return conn.execute(text("""
            SELECT * FROM users WHERE username = :u
        """), {"u": username}).fetchone()


def authenticate(username, password):
    user = get_user(username)

    if not user:
        return False

    return check_password(password, user.password)


# =========================================================
# 3. MSIG KNOWLEDGE BASE
# =========================================================
MSIG_KNOWLEDGE = {
    "FOAM_WHITE": {
        "Diagnosis": "Young Sludge / High F:M Ratio",
        "Action": "Reduce WAS to increase sludge age."
    },
    "FOAM_BROWN": {
        "Diagnosis": "Old Sludge / Nocardia",
        "Action": "Increase wasting + check grease."
    },
    "DARK_SEPTIC": {
        "Diagnosis": "Anaerobic / Low DO",
        "Action": "Increase aeration immediately."
    },
    "SYSTEM_OK": {
        "Diagnosis": "Normal Operation",
        "Action": "Maintain routine monitoring."
    }
}


# =========================================================
# 4. IMAGE ANALYSIS ENGINE
# =========================================================
def extract_features(img):
    image = np.array(img)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    foam = np.mean(gray > 200)
    dark = np.mean(gray < 50)

    return {
        "foam": foam,
        "dark": dark,
        "brightness": np.mean(gray)
    }


def visual_diagnosis(f):
    if f["dark"] > 0.4:
        return MSIG_KNOWLEDGE["DARK_SEPTIC"]
    if f["foam"] > 0.15:
        if f["brightness"] > 180:
            return MSIG_KNOWLEDGE["FOAM_WHITE"]
        else:
            return MSIG_KNOWLEDGE["FOAM_BROWN"]
    return MSIG_KNOWLEDGE["SYSTEM_OK"]


# =========================================================
# 5. PROCESS ENGINE
# =========================================================
def process_engine(data):
    findings = []
    actions = []

    sv30 = data["SV30"]
    do = data["DO"]
    mlss = data["MLSS"]
    nh3 = data["NH3"]

    svi = (sv30 / mlss) * 1000 if mlss else 0

    if do < 1.5:
        findings.append("Low DO")
        actions.append("Increase aeration")

    if svi > 150:
        findings.append("Bulking sludge")
        actions.append("Increase RAS")

    if nh3 > 10:
        findings.append("High ammonia load")
        actions.append("Improve nitrification")

    return {"findings": findings, "actions": actions, "svi": round(svi, 2)}


# =========================================================
# 6. HYDRAULIC CALC
# =========================================================
def tdh(static, flow, dia, length):
    C = 140
    Q = flow / 1000
    D = dia / 1000
    hf = 10.67 * (Q/C)**1.852 * (D**-4.87) * length
    return round(static + hf, 2)


# =========================================================
# 7. UI SETUP
# =========================================================
st.set_page_config("STP Smart Assist SaaS", layout="wide")

st.title("🌊 STP Smart Assist SaaS")

if DB_OK:
    st.success("🟢 Database Connected")
else:
    st.warning("⚠️ Database Offline Mode")


# =========================================================
# 8. LOGIN / REGISTER
# =========================================================
tab1, tab2 = st.tabs(["Login", "Register"])

with tab1:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if authenticate(u, p):
            st.session_state["user"] = u
            st.success("Login successful")
        else:
            st.error("Invalid login")


with tab2:
    ru = st.text_input("Username ", key="ru")
    rp = st.text_input("Password ", type="password", key="rp")
    rn = st.text_input("Name ")

    if st.button("Register"):
        if create_user(ru, rp, rn):
            st.success("Account created")
        else:
            st.error("DB not available")


# =========================================================
# 9. MAIN DASHBOARD (ONLY IF LOGGED IN)
# =========================================================
if "user" in st.session_state:

    st.header(f"Welcome {st.session_state['user']}")

    st.sidebar.header("Process Inputs")

    sv30 = st.sidebar.number_input("SV30", 250)
    do = st.sidebar.number_input("DO", 2.0)
    mlss = st.sidebar.number_input("MLSS", 3000)
    nh3 = st.sidebar.number_input("NH3", 5.0)

    data = {"SV30": sv30, "DO": do, "MLSS": mlss, "NH3": nh3}

    res = process_engine(data)

    st.subheader("Process Analysis")
    st.write(res["findings"])
    st.write(res["actions"])
    st.metric("SVI", res["svi"])

    st.subheader("Hydraulic Calc")
    st.write(tdh(5, 10, 100, 50))

    st.subheader("Image Analysis")
    img = st.file_uploader("Upload image", type=["jpg", "png"])

    if img:
        image = Image.open(img)
        feat = extract_features(image)
        diag = visual_diagnosis(feat)

        st.image(image)
        st.write(diag["Diagnosis"])
        st.write(diag["Action"])
