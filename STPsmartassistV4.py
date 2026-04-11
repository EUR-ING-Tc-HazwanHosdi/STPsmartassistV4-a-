import streamlit as st
import cv2
import numpy as np
from PIL import Image
import pandas as pd
import json
import os

# PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ---------------------------------------------------------
# CONFIG + UI
# ---------------------------------------------------------
st.set_page_config(page_title="MSIG Smart Assist Pro", layout="wide")

st.markdown("""
<style>
.stApp {background-color: #0E1117; color: white;}
.metric-card {background-color: #1F2933; padding: 20px; border-radius: 15px; text-align:center;}
.section-card {background-color: #1A1F24; padding: 20px; border-radius: 15px; margin-bottom: 15px;}
h1,h2,h3 {color:#00ADB5;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# SAFE USER SYSTEM (FIXED ERROR)
# ---------------------------------------------------------
def load_users():
    try:
        if not os.path.exists("users.json"):
            default_users = {
                "demo": {"password": "1234", "plan": "basic", "name": "Demo User"},
                "plant1": {"password": "1234", "plan": "premium", "name": "Plant Operator"}
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
    if user and user["password"] == password:
        return {"status": True, "plan": user["plan"], "name": user["name"]}
    return {"status": False}

# SESSION
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

# SIDEBAR
st.sidebar.title(f"👤 {user['name']}")
st.sidebar.write(f"Plan: {user['plan']}")

if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.rerun()

# ---------------------------------------------------------
# KNOWLEDGE BASE
# ---------------------------------------------------------
MSIG_KNOWLEDGE = {
    "FOAM_WHITE": {"Diagnosis": "Young Sludge", "Action": "Increase sludge age"},
    "FOAM_BROWN": {"Diagnosis": "Old Sludge", "Action": "Increase wasting"},
    "DARK_SEPTIC": {"Diagnosis": "Anaerobic", "Action": "Increase aeration"},
    "SYSTEM_OK": {"Diagnosis": "Normal", "Action": "Maintain operation"}
}

# ---------------------------------------------------------
# IMAGE ANALYSIS
# ---------------------------------------------------------
def extract_features(pil_image):
    image = np.array(pil_image)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    return {
        "foam": np.sum(edges > 0) / edges.size,
        "brightness": np.mean(gray),
        "dark_sludge": np.sum(gray < 40) / gray.size,
        "debug_mask": edges
    }

def msig_inference_engine(features):
    if features["dark_sludge"] > 0.45:
        return MSIG_KNOWLEDGE["DARK_SEPTIC"]
    if features["foam"] > 0.15:
        return MSIG_KNOWLEDGE["FOAM_WHITE"] if features["brightness"] > 180 else MSIG_KNOWLEDGE["FOAM_BROWN"]
    return MSIG_KNOWLEDGE["SYSTEM_OK"]

# ---------------------------------------------------------
# PROCESS ENGINE
# ---------------------------------------------------------
def process_inference_engine(data):
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

    elif svi < 80:
        findings.append("Young Sludge")
        actions.append("Reduce WAS")

    if nh3 > 10:
        findings.append("Incomplete Nitrification")
        actions.append("Increase aeration")

    if odour == "Septic (Rotten Egg)":
        findings.append("Anaerobic Condition")
        actions.append("Increase DO")

    if not findings:
        findings.append("Process Stable")
        actions.append("Maintain operation")

    return {"findings": findings, "actions": actions, "SVI": round(svi, 2)}

# ---------------------------------------------------------
# PDF (CLOUD SAFE)
# ---------------------------------------------------------
def generate_pdf(process_result):
    file_path = "/tmp/report.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("MSIG Smart Assist Report", styles['Title']))
    content.append(Spacer(1, 10))

    content.append(Paragraph(f"SVI: {process_result['SVI']}", styles['Normal']))

    content.append(Spacer(1, 10))
    content.append(Paragraph("Findings:", styles['Heading2']))

    for f in process_result["findings"]:
        content.append(Paragraph(f"- {f}", styles['Normal']))

    content.append(Spacer(1, 10))
    content.append(Paragraph("Actions:", styles['Heading2']))

    for a in process_result["actions"]:
        content.append(Paragraph(f"- {a}", styles['Normal']))

    doc.build(content)

    return file_path

# ---------------------------------------------------------
# INPUT
# ---------------------------------------------------------
st.title("🌊 MSIG Smart Assist Pro")

st.sidebar.header("🧪 Process Input")
sv30 = st.sidebar.number_input("SV30", value=250)
do = st.sidebar.number_input("DO", value=2.0)
mlss = st.sidebar.number_input("MLSS", value=3000)
nh3 = st.sidebar.number_input("NH3", value=5.0)
odour = st.sidebar.selectbox("Odour", ["None", "Septic (Rotten Egg)"])

data = {"SV30": sv30, "DO": do, "MLSS": mlss, "NH3": nh3, "ODOUR": odour}

# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------
col1, col2 = st.columns(2)

# IMAGE (Premium)
with col1:
    st.subheader("📸 Visual Analysis")

    if user["plan"] == "premium":
        file = st.file_uploader("Upload Image")

        if file:
            img = Image.open(file)
            features = extract_features(img)
            diag = msig_inference_engine(features)

            st.image(img)
            st.success(diag["Diagnosis"])
    else:
        st.warning("🔒 Premium feature")

# PROCESS
with col2:
    st.subheader("📊 Process Analysis")

    result = process_inference_engine(data)

    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.write(result["findings"])
    st.write(result["actions"])
    st.metric("SVI", result["SVI"])
    st.markdown("</div>", unsafe_allow_html=True)

# PDF
if user["plan"] == "premium":
    if st.button("📄 Generate PDF Report"):
        pdf = generate_pdf(result)
        with open(pdf, "rb") as f:
            st.download_button("⬇ Download Report", f, "report.pdf")
else:
    st.info("Upgrade to Premium for PDF report")
