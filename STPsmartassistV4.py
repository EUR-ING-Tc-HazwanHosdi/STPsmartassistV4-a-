import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pandas as pd
import json
import os
from datetime import datetime
import bcrypt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="MSIG Smart Assist Pro", layout="wide")

st.markdown("""
<style>
.stApp {background-color:#0E1117;color:white;}
.metric-card {background:#1F2933;padding:15px;border-radius:10px;}
.section-card {background:#1A1F24;padding:15px;border-radius:10px;margin-bottom:10px;}
h1,h2,h3 {color:#00ADB5;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# SAFE USER SYSTEM (bcrypt + auto-fix)
# ---------------------------------------------------------
def load_users():
    try:
        if not os.path.exists("users.json"):
            default_users = {
                "demo": {
                    "password": bcrypt.hashpw("1234".encode(), bcrypt.gensalt()).decode(),
                    "plan": "basic",
                    "name": "Demo User"
                },
                "plant1": {
                    "password": bcrypt.hashpw("1234".encode(), bcrypt.gensalt()).decode(),
                    "plan": "premium",
                    "name": "Plant Operator"
                }
            }
            with open("users.json", "w") as f:
                json.dump(default_users, f)

        with open("users.json", "r") as f:
            return json.load(f)

    except Exception as e:
        st.error(f"User system error: {e}")
        return {}

def authenticate(username, password):
    users = load_users()
    user = users.get(username)

    if user:
        stored_hash = user["password"].encode()
        if bcrypt.checkpw(password.encode(), stored_hash):
            return {"status": True, "plan": user["plan"], "name": user["name"]}

    return {"status": False}

# ---------------------------------------------------------
# SESSION
# ---------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

# LOGIN
if st.session_state.user is None:
    st.title("🔐 MSIG Smart Assist Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        result = authenticate(username, password)
        if result["status"]:
            st.session_state.user = result
            st.rerun()
        else:
            st.error("Invalid login")

    st.stop()

user = st.session_state.user

st.sidebar.title(f"👤 {user['name']}")
st.sidebar.write(f"Plan: {user['plan']}")

if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

# ---------------------------------------------------------
# ENGINE (MSIG + PROCESS)
# ---------------------------------------------------------
def extract_features(img):
    image = np.array(img)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    return {
        "foam": np.sum(edges > 0) / edges.size,
        "brightness": np.mean(gray),
        "dark_sludge": np.sum(gray < 40) / gray.size,
        "debug_mask": edges
    }

def msig_engine(features):
    if features["dark_sludge"] > 0.45:
        return "Anaerobic Condition"
    if features["foam"] > 0.15:
        return "Foaming Sludge"
    return "Normal"

def process_engine(data):
    findings, actions = [], []

    sv30 = data["SV30"]
    do = data["DO"]
    mlss = data["MLSS"]
    nh3 = data["NH3"]
    odour = data["ODOUR"]

    svi = sv30 / mlss * 1000 if mlss > 0 else 0

    if do < 1.5:
        findings.append("Low DO")
        actions.append("Increase aeration")

    if svi > 150:
        findings.append("Bulking Sludge")
        actions.append("Check filamentous bacteria")

    if nh3 > 10:
        findings.append("High Ammonia")
        actions.append("Increase nitrification")

    if odour == "Septic (Rotten Egg)":
        findings.append("Anaerobic Condition")
        actions.append("Increase DO")

    if not findings:
        findings.append("System Stable")
        actions.append("Maintain operation")

    return {"findings": findings, "actions": actions, "SVI": round(svi, 2)}

# ---------------------------------------------------------
# HISTORY + TREND SYSTEM
# ---------------------------------------------------------
def save_history(data, result):
    file = "history.csv"

    row = {
        "time": datetime.now(),
        "SV30": data["SV30"],
        "DO": data["DO"],
        "MLSS": data["MLSS"],
        "NH3": data["NH3"],
        "SVI": result["SVI"]
    }

    df = pd.DataFrame([row])

    if os.path.exists(file):
        df.to_csv(file, mode="a", header=False, index=False)
    else:
        df.to_csv(file, index=False)

# ---------------------------------------------------------
# PDF REPORT
# ---------------------------------------------------------
def generate_pdf(result):
    path = "/tmp/report.pdf"
    doc = SimpleDocTemplate(path)
    styles = getSampleStyleSheet()

    content = []
    content.append(Paragraph("MSIG Smart Assist Report", styles["Title"]))
    content.append(Spacer(1, 10))

    content.append(Paragraph(f"SVI: {result['SVI']}", styles["Normal"]))
    content.append(Spacer(1, 10))

    content.append(Paragraph("Findings:", styles["Heading2"]))
    for f in result["findings"]:
        content.append(Paragraph(f"- {f}", styles["Normal"]))

    content.append(Paragraph("Actions:", styles["Heading2"]))
    for a in result["actions"]:
        content.append(Paragraph(f"- {a}", styles["Normal"]))

    doc.build(content)
    return path

# ---------------------------------------------------------
# INPUTS
# ---------------------------------------------------------
st.title("🌊 MSIG Smart Assist Pro (SaaS)")

st.sidebar.header("Process Input")
data = {
    "SV30": st.sidebar.number_input("SV30", 250),
    "DO": st.sidebar.number_input("DO", 2.0),
    "MLSS": st.sidebar.number_input("MLSS", 3000),
    "NH3": st.sidebar.number_input("NH3", 5.0),
    "ODOUR": st.sidebar.selectbox("Odour", ["None", "Septic (Rotten Egg)"])
}

# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------
col1, col2 = st.columns(2)

# IMAGE MODULE (Premium)
with col1:
    st.subheader("📸 Image Analysis")

    if user["plan"] == "premium":
        img_file = st.file_uploader("Upload Image")

        if img_file:
            img = Image.open(img_file)
            features = extract_features(img)
            diag = msig_engine(features)

            st.image(img)
            st.success(diag)
    else:
        st.warning("Premium feature locked")

# PROCESS MODULE
with col2:
    st.subheader("📊 Process Analysis")

    result = process_engine(data)

    st.write(result["findings"])
    st.write(result["actions"])
    st.metric("SVI", result["SVI"])

# ---------------------------------------------------------
# TREND + SAVE
# ---------------------------------------------------------
if st.button("💾 Save Data"):
    save_history(data, result)
    st.success("Saved!")

if os.path.exists("history.csv"):
    hist = pd.read_csv("history.csv")
    st.subheader("📈 Trend Analysis")
    st.line_chart(hist.set_index("time")[["DO", "SVI"]])

# ---------------------------------------------------------
# PDF (Premium)
# ---------------------------------------------------------
if user["plan"] == "premium":
    if st.button("📄 Generate Report"):
        pdf = generate_pdf(result)
        with open(pdf, "rb") as f:
            st.download_button("Download PDF", f, "report.pdf")
else:
    st.info("Upgrade to Premium for PDF export")
