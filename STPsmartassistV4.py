import streamlit as st
import numpy as np
import pandas as pd
import cv2
from PIL import Image
from datetime import datetime
import bcrypt
import requests
import base64
from sqlalchemy import create_engine

# =========================================================
# CONFIG
# =========================================================
st.set_page_config("STP Smart Assist SaaS", layout="wide")

# =========================================================
# DATABASE (PostgreSQL / Supabase)
# =========================================================
DATABASE_URL = "postgresql://USER:PASS@HOST:5432/DB"

try:
    engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
    DB_MODE = True
except:
    DB_MODE = False
    st.warning("Database offline mode enabled")

# =========================================================
# PAYPAL CONFIG
# =========================================================
PAYPAL_CLIENT_ID = "YOUR_ID"
PAYPAL_SECRET = "YOUR_SECRET"
PAYPAL_BASE = "https://api-m.paypal.com"

PRICING = {
    "pro": "29.00",
    "premium": "99.00",
    "enterprise": "199.00"
}

# =========================================================
# SECURITY
# =========================================================
def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_password(p, h):
    return bcrypt.checkpw(p.encode(), h.encode())

# =========================================================
# REGISTER USER
# =========================================================
def register_user(username, password, name):
    if not DB_MODE:
        return {"status": False, "msg": "DB not available"}

    try:
        with engine.begin() as conn:
            conn.execute("""
                INSERT INTO users (username, password, name, plan)
                VALUES (%s,%s,%s,'basic')
            """, (username, hash_password(password), name))

        return {"status": True}

    except Exception as e:
        return {"status": False, "msg": str(e)}

# =========================================================
# LOGIN USER
# =========================================================
def authenticate(username, password):
    if not DB_MODE:
        return {"status": False}

    with engine.begin() as conn:
        user = conn.execute("""
            SELECT username, password, name, plan
            FROM users WHERE username=%s
        """, (username,)).fetchone()

    if user and check_password(password, user[1]):
        return {
            "status": True,
            "username": user[0],
            "name": user[2],
            "plan": user[3]
        }

    return {"status": False}

# =========================================================
# PAYPAL TOKEN
# =========================================================
def get_token():
    auth = base64.b64encode(
        f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}".encode()
    ).decode()

    r = requests.post(
        f"{PAYPAL_BASE}/v1/oauth2/token",
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"}
    )
    return r.json()["access_token"]

# =========================================================
# CREATE PAYMENT
# =========================================================
def create_payment(plan, username):
    token = get_token()

    r = requests.post(
        f"{PAYPAL_BASE}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": "MYR",
                    "value": PRICING[plan]
                },
                "description": f"{plan} plan upgrade"
            }]
        }
    )

    order = r.json()

    if DB_MODE:
        with engine.begin() as conn:
            conn.execute("""
                INSERT INTO payments (username, plan, paypal_order_id, status)
                VALUES (%s,%s,%s,'PENDING')
            """, (username, plan, order["id"]))

    return order

# =========================================================
# AUTO PAYMENT CHECK (NO WEBHOOK)
# =========================================================
def check_payments():
    if not DB_MODE:
        return

    token = get_token()

    with engine.begin() as conn:
        rows = conn.execute("""
            SELECT username, plan, paypal_order_id
            FROM payments WHERE status='PENDING'
        """).fetchall()

    for r in rows:
        username, plan, order_id = r

        res = requests.get(
            f"{PAYPAL_BASE}/v2/checkout/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"}
        ).json()

        if res.get("status") == "COMPLETED":
            with engine.begin() as conn:
                conn.execute("""
                    UPDATE payments SET status='PAID'
                    WHERE paypal_order_id=%s
                """, (order_id,))

                conn.execute("""
                    UPDATE users SET plan=%s
                    WHERE username=%s
                """, (plan, username))

# =========================================================
# ENGINE (YOUR STP SYSTEM)
# =========================================================
def process_engine(data):
    svi = data["SV30"] / data["MLSS"] * 1000

    findings, actions = [], []

    if data["DO"] < 1.5:
        findings.append("Low DO")
        actions.append("Increase aeration")

    if svi > 150:
        findings.append("Bulking Sludge")
        actions.append("Check filaments")

    if data["NH3"] > 10:
        findings.append("High NH3")
        actions.append("Increase nitrification")

    if not findings:
        findings.append("System Stable")
        actions.append("Maintain operation")

    return {
        "SVI": round(svi, 2),
        "findings": findings,
        "actions": actions
    }

# =========================================================
# IMAGE ANALYSIS
# =========================================================
def image_engine(img):
    img = np.array(img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    foam = np.sum(edges > 0) / edges.size

    return "Foaming Sludge" if foam > 0.15 else "Normal"

# =========================================================
# SESSION
# =========================================================
if "user" not in st.session_state:
    st.session_state.user = None

# =========================================================
# AUTH UI
# =========================================================
if st.session_state.user is None:
    st.title("🔐 STP Smart Assist SaaS")

    mode = st.radio("Mode", ["Login", "Register"])

    if mode == "Register":
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        n = st.text_input("Name")

        if st.button("Create"):
            res = register_user(u, p, n)
            if res["status"]:
                st.success("Account created")
            else:
                st.error(res.get("msg"))

    if mode == "Login":
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
# USER SESSION
# =========================================================
user = st.session_state.user

# =========================================================
# AUTO CHECK PAYMENTS
# =========================================================
check_payments()

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title(user["name"])
st.sidebar.write("Plan:", user["plan"])

if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

# =========================================================
# UPGRADE SYSTEM
# =========================================================
if user["plan"] != "premium":
    plan = st.sidebar.selectbox("Upgrade", list(PRICING.keys()))

    if st.sidebar.button("Pay with PayPal"):
        order = create_payment(plan, user["username"])

        for link in order["links"]:
            if link["rel"] == "approve":
                st.sidebar.markdown(f"[Pay Now]({link['href']})")

# =========================================================
# DASHBOARD INPUTS
# =========================================================
st.title("🌊 STP Dashboard")

data = {
    "SV30": st.sidebar.number_input("SV30", 250),
    "DO": st.sidebar.number_input("DO", 2.0),
    "MLSS": st.sidebar.number_input("MLSS", 3000),
    "NH3": st.sidebar.number_input("NH3", 5.0)
}

result = process_engine(data)

# =========================================================
# DASHBOARD UI
# =========================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("Process Analysis")
    st.write(result["findings"])
    st.write(result["actions"])
    st.metric("SVI", result["SVI"])

with col2:
    st.subheader("AI Visual")

    if user["plan"] in ["premium", "enterprise"]:
        file = st.file_uploader("Upload Image")
        if file:
            img = Image.open(file)
            st.image(img)
            st.success(image_engine(img))
    else:
        st.warning("Upgrade required")

# =========================================================
# HISTORY (OPTIONAL DB FEATURE)
# =========================================================
if DB_MODE and user["plan"] != "basic":
    if st.button("Save Record"):
        with engine.begin() as conn:
            conn.execute("""
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
