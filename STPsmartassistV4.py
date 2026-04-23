import streamlit as st
import numpy as np
import cv2
from PIL import Image
import streamlit.components.v1 as components
import json
import os
import hashlib

# =========================================================
# STREAMLIT CONFIG
# =========================================================
st.set_page_config("STP Smart Assist Pro", layout="wide")

# =========================================================
# USER DATABASE (LOCAL JSON)
# =========================================================
USER_DB_FILE = "users.json"

def load_users():
    if not os.path.exists(USER_DB_FILE):
        return {}
    with open(USER_DB_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =========================================================
# SESSION INIT
# =========================================================
if "user" not in st.session_state:
    st.session_state["user"] = None

user = st.session_state["user"]

# =========================================================
# AUTH SYSTEM
# =========================================================
def get_user(username):
    users = load_users()
    return users.get(username)

def create_user(username, password, name):
    users = load_users()

    if username in users:
        return False

    users[username] = {
        "username": username,
        "password": hash_password(password),
        "name": name,
        "is_paid": False
    }

    save_users(users)
    return True

def authenticate(username, password):
    user = get_user(username)

    if not user:
        return False

    return user["password"] == hash_password(password)

# =========================================================
# PAYPAL (OPTIONAL - NOT FORCING ANY LIMIT)
# =========================================================
def render_paypal_button(user_email):
    paypal_html = """
    <div id="paypal-button-container"></div>

    <script src="https://www.paypal.com/sdk/js?client-id=YOUR_CLIENT_ID&vault=true&intent=subscription"></script>

    <script>
    paypal.Buttons({
        createSubscription: function(data, actions) {
            return actions.subscription.create({
                plan_id: 'YOUR_PLAN_ID'
            });
        },
        onApprove: function(data, actions) {
            alert("Subscription successful!");
        }
    }).render('#paypal-button-container');
    </script>
    """
    components.html(paypal_html, height=400)

# =========================================================
# STP DIAGNOSIS ENGINE
# =========================================================
def stp_diagnosis(sv30, do, mlss, nh3, svi):

    issues = []
    actions = []
    severity = "🟢 Normal"

    if do < 1.5:
        issues.append("Low Dissolved Oxygen (DO)")
        actions.append("Increase aeration (2.0–3.0 mg/L)")
        severity = "🔴 Critical"

    if svi > 150:
        issues.append("Bulking Sludge Condition")
        actions.append("Increase sludge wasting (WAS)")
        severity = "🟠 Warning"

    if nh3 > 10:
        issues.append("High Ammonia Load")
        actions.append("Increase aeration + retention time")
        severity = "🟠 Warning"

    if mlss < 1500:
        issues.append("Low Biomass")
        actions.append("Reduce sludge wasting")

    if mlss > 5000:
        issues.append("High MLSS")
        actions.append("Increase sludge wasting")

    if not issues:
        issues.append("System Operating Normally")
        actions.append("Maintain monitoring")

    return severity, issues, actions

# =========================================================
# IMAGE ANALYSIS
# =========================================================
def extract_features(img):
    image = np.array(img)
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    return {
        "foam": np.mean(gray > 200),
        "dark": np.mean(gray < 60),
        "brightness": np.mean(gray),
        "texture": cv2.Laplacian(gray, cv2.CV_64F).var()
    }

def diagnose(features):

    if features["dark"] > 0.4:
        return {"Diagnosis": "Anaerobic Condition", "Action": "Increase aeration"}

    if features["foam"] > 0.15:
        return {"Diagnosis": "Foaming Detected", "Action": "Check FOG loading"}

    if features["texture"] < 40:
        return {"Diagnosis": "Low Activity", "Action": "Check MLSS"}

    return {"Diagnosis": "Normal Condition", "Action": "Maintain operation"}

# =========================================================
# UI HEADER
# =========================================================
st.title("🌊 STP Smart Assist Pro")
st.success("🟢 System Active (Unlimited Access Mode)")

# =========================================================
# LOGIN / REGISTER
# =========================================================
tab1, tab2 = st.tabs(["Login", "Register"])

with tab1:
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if authenticate(u, p):
            st.session_state["user"] = get_user(u)
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid credentials")

with tab2:
    ru = st.text_input("Username", key="ru")
    rp = st.text_input("Password", type="password", key="rp")
    rn = st.text_input("Name")

    if st.button("Register"):
        if create_user(ru, rp, rn):
            st.success("Account created")
        else:
            st.error("User already exists")

# =========================================================
# SESSION CHECK
# =========================================================
user = st.session_state.get("user")

if not user:
    st.info("🔐 Please login to access system")
    st.stop()

st.header(f"Welcome {user.get('name')}")

# =========================================================
# PLAN STATUS (NO LIMITS)
# =========================================================
if user.get("is_paid"):
    st.success("🟢 Pro User")
else:
    st.warning("🟡 Free User (No Restrictions)")

if st.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()

# =========================================================
# INPUTS
# =========================================================
sv30 = st.number_input("SV30", value=250.0)
do = st.number_input("DO", value=2.0)
mlss = st.number_input("MLSS", value=3000.0)
nh3 = st.number_input("NH3", value=5.0)

svi = (sv30 / mlss) * 1000 if mlss else 0

# =========================================================
# BASIC DIAGNOSIS
# =========================================================
st.subheader("🧠 Process Diagnosis")

severity, issues, actions = stp_diagnosis(sv30, do, mlss, nh3, svi)

st.markdown(f"### Status: {severity}")

for i in issues:
    st.write("•", i)

for a in actions:
    st.write("•", a)

st.metric("SVI", round(svi, 2))

# =========================================================
# ADVANCED SECTION (UNLOCKED LOGIC ONLY)
# =========================================================
st.subheader("🔬 Advanced AI Analysis")

st.success("Advanced features available (no restriction mode)")

adv_score = 100 - abs(150 - svi)
st.metric("Stability Score", round(adv_score, 2))

# =========================================================
# IMAGE ANALYSIS
# =========================================================
st.subheader("📷 Image Analysis")

img = st.file_uploader("Upload image", type=["jpg", "png"])

if img:
    image = Image.open(img)
    features = extract_features(image)
    result = diagnose(features)

    st.image(image)
    st.write("Diagnosis:", result["Diagnosis"])
    st.write("Action:", result["Action"])

    st.success("Advanced image analysis enabled")
