import streamlit as st
import requests
import numpy as np
import cv2
from PIL import Image

# =========================================================
# 1. SUPABASE CONFIG (API MODE - NO POSTGRES)
# =========================================================
SUPABASE_URL = "https://imyaqnitshcwfplyfotl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlteWFxbml0c2hjd2ZwbHlmb3RsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU4OTc5MjMsImV4cCI6MjA5MTQ3MzkyM30.VRHmKYGPMl3QQVXY45UMbGWuYCB6GFgqoC6Jo9RE9ws"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# =========================================================
# 2. AUTH (SUPABASE REST API)
# =========================================================
def get_user(username):
    url = f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}"

    r = requests.get(url, headers=headers)

    try:
        data = r.json()
    except Exception as e:
        st.error(f"Invalid API response: {e}")
        return None

    # 🔥 HANDLE ERROR RESPONSE (DICT)
    if isinstance(data, dict):
        st.error(f"Supabase Error: {data}")
        return None

    # 🔥 HANDLE EMPTY LIST
    if isinstance(data, list) and len(data) > 0:
        return data[0]

    return None


def create_user(username, password, name, plan="free"):
    url = f"{SUPABASE_URL}/rest/v1/users"

    payload = {
        "username": username,
        "password": password,
        "name": name,
        "plan": plan
    }

    r = requests.post(url, json=payload, headers=headers)
    return r.status_code == 201


def authenticate(username, password):
    user = get_user(username)

    if not user:
        return False

    return user.get("password") == password


# =========================================================
# 3. STP KNOWLEDGE BASE (YOUR SYSTEM)
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
        "Action": "Maintain monitoring."
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


def diagnose(features):
    if features["dark"] > 0.4:
        return MSIG_KNOWLEDGE["DARK_SEPTIC"]

    if features["foam"] > 0.15:
        if features["brightness"] > 180:
            return MSIG_KNOWLEDGE["FOAM_WHITE"]
        else:
            return MSIG_KNOWLEDGE["FOAM_BROWN"]

    return MSIG_KNOWLEDGE["SYSTEM_OK"]

def stp_diagnosis(sv30, do, mlss, nh3, svi):

    issues = []
    actions = []
    severity = "🟢 Normal"

    # LOW DO
    if do < 1.5:
        issues.append("Low Dissolved Oxygen (DO)")
        actions.append("Increase aeration immediately (target 2.0–3.0 mg/L)")
        severity = "🔴 Critical"

    # BULKING SLUDGE
    if svi > 150:
        issues.append("Bulking Sludge Condition")
        actions.append("Increase sludge wasting (WAS) and check F/M ratio")
        severity = "🟠 Warning"

    # HIGH AMMONIA
    if nh3 > 10:
        issues.append("High Ammonia Load (Poor Nitrification)")
        actions.append("Increase aeration + extend aeration time")
        severity = "🟠 Warning"

    # LOW MLSS
    if mlss < 1500:
        issues.append("Low Biomass Concentration")
        actions.append("Reduce sludge wasting to build biomass")

    # HIGH MLSS
    if mlss > 5000:
        issues.append("High MLSS (Overloaded System)")
        actions.append("Increase sludge wasting and balance F/M ratio")

    # STABLE CONDITION
    if not issues:
        issues.append("System Operating Normally")
        actions.append("Maintain current operation and monitoring")

    return severity, issues, actions
# =========================================================
# 5. STREAMLIT UI
# =========================================================
st.set_page_config("STP Smart Assist SaaS", layout="wide")

st.title("🌊 STP Smart Assist SaaS (API Mode)")

# DB INFO (API MODE = ALWAYS ONLINE)
st.success("🟢 API Backend Active (No Database Connection Errors)")


# =========================================================
# 6. LOGIN / REGISTER
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
            st.error("Invalid credentials")


with tab2:
    ru = st.text_input("Username ", key="ru")
    rp = st.text_input("Password ", type="password", key="rp")
    rn = st.text_input("Name ")

    if st.button("Register"):
        if create_user(ru, rp, rn):
            st.success("Account created")
        else:
            st.error("Registration failed")


# =========================================================
# 7. MAIN DASHBOARD
# =========================================================
if "user" in st.session_state:

    st.header(f"Welcome {st.session_state['user']}")

    sv30 = st.number_input("SV30", 250)
    do = st.number_input("DO", 2.0)
    mlss = st.number_input("MLSS", 3000)
    nh3 = st.number_input("NH3", 5.0)

    svi = (sv30 / mlss) * 1000 if mlss else 0

    st.subheader("🧠 Intelligent Process Diagnosis")

svi = (sv30 / mlss) * 1000 if mlss else 0

severity, issues, actions = stp_diagnosis(sv30, do, mlss, nh3, svi)

# STATUS
st.markdown(f"### System Status: {severity}")

# DIAGNOSIS
st.markdown("### 🔍 Diagnosis")
for i in issues:
    st.write("•", i)

# ACTIONS
st.markdown("### ⚡ Recommended Actions")
for a in actions:
    st.write("•", a)

# METRICS
st.metric("SVI", round(svi, 2))
st.subheader("Image Analysis")

    img = st.file_uploader("Upload image", type=["jpg", "png"])

    if img:
        image = Image.open(img)
        features = extract_features(image)
        result = diagnose(features)

        st.image(image)
        st.write(result["Diagnosis"])
        st.write(result["Action"])
