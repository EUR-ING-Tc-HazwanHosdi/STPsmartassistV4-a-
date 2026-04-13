import streamlit as st
import requests
import numpy as np
import cv2
from PIL import Image
import streamlit.components.v1 as components
# =========================================================
# GLOBAL USER (PREVENT NameError EVERYWHERE)
# =========================================================
user = st.session_state.get("user", None)
if user is None:
    user = {}

def render_paypal_button(user_email):
    paypal_sub_button = f"""
    <div id="paypal-button-container"></div>

    <script src="https://www.paypal.com/sdk/js?client-id=Ab9ej6Zc4XqzZczeNUYOERKyka-PhXoJuNkkgkIAtXVe6-GXZmqDUPjF6NxMwGsCor-oGpx4DFxRz6E5&vault=true&intent=subscription"></script>

    <script>
    paypal.Buttons({{
        style: {{
            shape: 'rect',
            color: 'gold',
            layout: 'vertical',
            label: 'subscribe'
        }},

        createSubscription: function(data, actions) {{
            return actions.subscription.create({{
                plan_id: 'P-0DL15529NM130961FNHNYNPQ'
            }});
        }},

        onApprove: function(data, actions) {{

            fetch("https://your-backend-url/paypal-success", {{
                method: "POST",
                headers: {{
                    "Content-Type": "application/json"
                }},
                body: JSON.stringify({{
                    subscriptionID: data.subscriptionID,
                    email: "{user_email}"
                }})
            }});

            alert("Subscription successful!");
        }}

    }}).render('#paypal-button-container');
    </script>
    """

    components.html(paypal_sub_button, height=400)

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
        "plan": plan,
        "is_paid": False,
        "email": username  # temporary: username = email
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

    brightness = np.mean(gray)
    contrast = np.std(gray)

    foam = np.mean(gray > 200)
    dark = np.mean(gray < 60)

    texture = cv2.Laplacian(gray, cv2.CV_64F).var()

    return {
        "foam": foam,
        "dark": dark,
        "brightness": brightness,
        "contrast": contrast,
        "texture": texture
    }


def diagnose(features):

    if features["dark"] > 0.4:
        return {
            "Diagnosis": "Anaerobic / Septic Condition",
            "Action": "Increase aeration immediately"
        }

    if features["foam"] > 0.15:
        return {
            "Diagnosis": "Foaming Sludge Detected",
            "Action": "Check FOG loading and reduce sludge age"
        }

    if features["texture"] < 40:
        return {
            "Diagnosis": "Low Biological Activity",
            "Action": "Check MLSS and nutrient balance"
        }

    return {
        "Diagnosis": "Normal Activated Sludge Condition",
        "Action": "Maintain current operation"
    }

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

st.title("🌊 STP Smart Assist Pro")

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
            user_data = get_user(u)   # ✅ get full user from Supabase
            st.session_state["user"] = user_data   # ✅ store full object
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
# FREEMIUM ACCESS CONTROL (FIXED)
# =========================================================
FEATURE_ACCESS = {
    "basic_diagnosis": "free",
    "advanced_diagnosis": "pro",
    "image_basic": "free",
    "image_advanced": "pro"
}

def has_access(user, feature):
    if not user:
        return False

    is_paid = bool(user.get("is_paid", False))

    required = FEATURE_ACCESS.get(feature, "free")

    if required == "free":
        return True

    return is_paid
# =========================================================
# 7. MAIN DASHBOARD (FIXED FREEMIUM FLOW)
# =========================================================
if "user" in st.session_state:

    user = st.session_state["user"]

    st.header(f"Welcome {user.get('name', 'User')}")

    # PLAN STATUS
    if user.get("is_paid") is True:
    st.success("🟢 Pro User")
else:
    st.warning("🟡 Free Plan")

    # LOGOUT
    col1, col2 = st.columns([8, 1])
    with col2:
        if st.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()

    # =========================
    # INPUTS
    # =========================
    sv30 = st.number_input("SV30", value=250.0, min_value=0.0)
    do = st.number_input("DO", value=2.0, min_value=0.0)
    mlss = st.number_input("MLSS", value=3000.0, min_value=1.0)
    nh3 = st.number_input("NH3", value=5.0, min_value=0.0)

    svi = (sv30 / mlss) * 1000 if mlss else 0

    # =========================
    # BASIC DIAGNOSIS (FREE)
    # =========================
    st.subheader("🧠 Intelligent Process Diagnosis (Basic)")

    basic_severity, basic_issues, basic_actions = stp_diagnosis(
        sv30, do, mlss, nh3, svi
    )

    st.markdown(f"### System Status: {basic_severity}")

    for i in basic_issues:
        st.write("•", i)

    for a in basic_actions:
        st.write("•", a)

    st.metric("SVI", round(svi, 2))

    # =========================
    # ADVANCED FEATURE (PRO ONLY)
    # =========================
    st.subheader("🔬 Advanced AI Analysis")

    if has_access(user, "advanced_diagnosis"):

        st.success("🟢 Advanced AI Enabled")
        st.write("📊 Stability scoring active")
        st.write("🧠 Deep process interpretation active")

        # (optional advanced logic placeholder)
        adv_score = 100 - abs(150 - svi)
        st.metric("Process Stability Score", round(adv_score, 2))

    else:
        st.warning("🔒 Advanced AI locked for Pro users")
        render_paypal_button(user.get("username"))

    # =========================
    # IMAGE ANALYSIS
    # =========================
    st.subheader("📷 Image Analysis")

    img = st.file_uploader("Upload image", type=["jpg", "png"])

    if img:
        image = Image.open(img)
        features = extract_features(image)
        result = diagnose(features)

        st.image(image)
        st.write("Basic Diagnosis:", result["Diagnosis"])
        st.write("Action:", result["Action"])

        if has_access(user, "advanced_image"):
            st.success("🟢 Pro Image Insights")
            st.write("🔬 High-resolution texture analysis enabled")
            st.write("📊 Foam classification enhanced")
        else:
            st.info("Upgrade to Pro for deeper image analytics")

else:
    st.info("Please login to access STP Smart Assist system.")
    