import streamlit as st
import pandas as pd
from datetime import datetime
from PIL import Image
import requests
import base64
import io
import re
import urllib.parse
from supabase import create_client, Client

st.set_page_config(
    page_title="Cardly",
    page_icon="🏈",
    layout="centered"
)

# ---------- SPACE BACKGROUND STYLING ----------
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(ellipse at bottom, #1b2735 0%, #090a0f 100%);
        color: white;
    }
    
    .stApp::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: 
            radial-gradient(2px 2px at 20px 30px, #eee, rgba),
            radial-gradient(2px 2px at 40px 70px, #fff, rgba),
            radial-gradient(1px 1px at 90px 40px, #fff, rgba),
            radial-gradient(1px 1px at 130px 80px, #fff, rgba),
            radial-gradient(2px 2px at 160px 120px, #ddd, rgba);
        background-repeat: repeat;
        background-size: 200px 200px;
        opacity: 0.25;
        pointer-events: none;
        z-index: 0;
    }

    h1, h2, h3, p, label, .stMarkdown {
        color: white !important;
    }
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        background-color: rgba(30, 30, 47, 0.85);
        color: white;
    }
    .stButton > button {
        background-color: #4f46e5;
        color: white;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ---------- SUPABASE ----------
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ---------- SESSION STATE ----------
if "user" not in st.session_state:
    st.session_state.user = None
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=[
        "card_name", "set", "year", "parallel", "grade",
        "beckett", "ebay_active", "date_added"
    ])

# ---------- HELPER FUNCTIONS ----------
def get_ocr_space_text(image):
    try:
        api_key = st.secrets["OCR_SPACE_API_KEY"]
    except Exception:
        return []

    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    payload = {
        "apikey": api_key,
        "base64Image": f"data:image/jpeg;base64,{img_str}",
        "language": "eng",
        "isOverlayRequired": False,
        "OCREngine": 2
    }

    try:
        r = requests.post("https://api.ocr.space/parse/image", data=payload, timeout=30)
        result = r.json()
        if result.get("IsErroredOnProcessing"):
            return []
        parsed = result.get("ParsedResults", [])
        if parsed:
            text = parsed[0].get("ParsedText", "")
            return [x.strip() for x in text.split("\n") if x.strip()]
        return []
    except Exception:
        return []

def analyze_card_text(texts):
    full = " ".join(texts).lower()
    card_name = ""
    set_name = ""
    year = 2024
    parallel = "Base"

    year_match = re.search(r"\b(202[0-6])\b", full)
    if year_match:
        year = int(year_match.group(1))

    sets = {
        "prizm": "Panini Prizm",
        "optic": "Donruss Optic",
        "mosaic": "Panini Mosaic",
        "select": "Panini Select",
        "donruss": "Donruss",
        "topps": "Topps",
        "chrome": "Topps Chrome",
        "bowman": "Bowman"
    }

    for key, val in sets.items():
        if key in full:
            set_name = f"{year} {val}"
            break

    parallels = ["silver", "gold", "prizm", "holo", "refractor", "green", "blue", "red"]
    for p in parallels:
        if p in full:
            parallel = p.title()
            break

    ignore = {"panini", "prizm", "optic", "mosaic", "select", "donruss", "topps", "the", "of", "and", "rookie", "rc", "card"}
    candidates = [t.strip() for t in texts if len(t.strip()) > 5 and not any(w in t.lower() for w in ignore)]
    if candidates:
        card_name = sorted(candidates, key=len, reverse=True)[0]

    if ("rookie" in full or "rc" in full) and card_name and "rookie" not in card_name.lower():
        card_name += " Rookie"

    return {"card_name": card_name, "set": set_name, "year": year, "parallel": parallel, "raw_text": texts}

def make_links(card_name, set_name, year, parallel):
    query = f"{year} {set_name} {card_name} {parallel} PSA BGS".strip()
    query = re.sub(r'\s+', ' ', query)
    encoded = urllib.parse.quote(query)
    ebay_active = f"https://www.ebay.com/sch/i.html?_nkw={encoded}"

    slug = f"{year}-{set_name}".lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    beckett = f"https://www.beckett.com/news/{slug}-cards/"

    return beckett, ebay_active

def load_user_portfolio(user_id: str):
    try:
        res = supabase.table("portfolios").select("cards").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0 and res.data[0]["cards"]:
            return pd.DataFrame(res.data[0]["cards"])
        return pd.DataFrame(columns=["card_name", "set", "year", "parallel", "grade", "beckett", "ebay_active", "date_added"])
    except Exception as e:
        st.error(f"Error loading portfolio: {e}")
        return pd.DataFrame(columns=["card_name", "set", "year", "parallel", "grade", "beckett", "ebay_active", "date_added"])

def save_user_portfolio(user_id: str, df: pd.DataFrame):
    try:
        cards = df.to_dict(orient="records")
        existing = supabase.table("portfolios").select("id").eq("user_id", user_id).execute()
        if existing.data:
            supabase.table("portfolios").update({
                "cards": cards,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("user_id", user_id).execute()
        else:
            supabase.table("portfolios").insert({
                "user_id": user_id,
                "cards": cards
            }).execute()
    except Exception as e:
        st.error(f"Error saving portfolio: {e}")

# ---------- LOGIN PAGE ----------
def show_login_page():
    st.title("🏈⚾ Cardly 🏀🏒")
    st.caption("Sign in to save and manage your sports card portfolio")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.link_button("Beckett", "https://www.beckett.com", use_container_width=True)
    with c2:
        st.link_button("PSA", "https://www.psacard.com", use_container_width=True)
    with c3:
        st.link_button("Ebay", "https://www.ebay.com", use_container_width=True)

    st.divider()

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.user = res.user
                    st.session_state.portfolio = load_user_portfolio(res.user.id)
                    st.success("Logged in!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with tab2:
        with st.form("signup_form"):
            email = st.text_input("Email", key="su_email")
            password = st.text_input("Password", type="password", key="su_pass")
            if st.form_submit_button("Create Account", use_container_width=True):
                try:
                    supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Account created! Check your email to confirm, then log in.")
                except Exception as e:
                    st.error(f"Sign up failed: {e}")

# ---------- MAIN APP ----------
def show_main_app():
    st.title("🏈⚾ Cardly 🏀🏒")
    st.caption(f"Logged in as {st.session_state.user.email}")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.link_button("Beckett", "https://www.beckett.com", use_container_width=True)
    with c2:
        st.link_button("PSA", "https://www.psacard.com", use_container_width=True)
    with c3:
        st.link_button("Ebay", "https://www.ebay.com", use_container_width=True)

    if st.button("Log out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.portfolio = pd.DataFrame()
        st.rerun()

    st.divider()

    st.subheader("📸 Add New Card")
    uploaded = st.file_uploader("Upload or take a photo of the card", type=["jpg", "jpeg", "png"])
    analysis = None

    if uploaded is not None:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, caption="Uploaded Card", use_container_width=True)

        with st.spinner("Reading card with OCR..."):
            texts = get_ocr_space_text(image)
            if texts:
                analysis = analyze_card_text(texts)

        if analysis and analysis.get("raw_text"):
            with st.expander("Raw text detected by AI"):
                st.write(analysis["raw_text"])

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            card_name = st.text_input("Card Name", value=analysis["card_name"] if analysis else "")
            set_name = st.text_input("Set", value=analysis["set"] if analysis else "")
            year = st.number_input("Year", value=analysis["year"] if analysis else 2024, min_value=1980, max_value=2026)
        with c2:
            parallel = st.text_input("Parallel", value=analysis["parallel"] if analysis else "Base")
            grade = st.number_input("Grade", value=9.5, min_value=1.0, max_value=10.0, step=0.5)

        if st.form_submit_button("Add to Portfolio", use_container_width=True):
            if not card_name.strip():
                st.error("Please enter a Card Name")
            else:
                beckett, ebay_active = make_links(card_name, set_name, year, parallel)
                new_row = {
                    "card_name": card_name.strip(),
                    "set": set_name.strip() if set_name else "Unknown Set",
                    "year": year,
                    "parallel": parallel.strip() if parallel else "Base",
                    "grade": grade,
                    "beckett": beckett,
                    "ebay_active": ebay_active,
                    "date_added": datetime.now().strftime("%Y-%m-%d")
                }
                st.session_state.portfolio = pd.concat(
                    [st.session_state.portfolio, pd.DataFrame([new_row])], ignore_index=True
                )
                save_user_portfolio(st.session_state.user.id, st.session_state.portfolio)
                st.success(f"Added {card_name}")

    st.subheader("Your Portfolio")
    df = st.session_state.portfolio

    if len(df) > 0:
        st.metric("Cards", len(df))
        st.dataframe(
            df[["card_name", "set", "parallel", "grade", "beckett", "ebay_active"]],
            column_config={
                "beckett": st.column_config.LinkColumn("Beckett", display_text="Beckett"),
                "ebay_active": st.column_config.LinkColumn("eBay", display_text="eBay")
            },
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")
        st.write("**Delete a card**")
        options = [f"{i+1}. {row['card_name']} ({row['set']})" for i, row in df.iterrows()]
        selected = st.selectbox("Select card to delete", options)
        if st.button("Delete Selected Card", type="primary"):
            idx = int(selected.split(".")[0]) - 1
            st.session_state.portfolio = df.drop(idx).reset_index(drop=True)
            save_user_portfolio(st.session_state.user.id, st.session_state.portfolio)
            st.success("Card deleted")
            st.rerun()
    else:
        st.info("No cards yet. Add your first card above.")

# ---------- ROUTING ----------
if st.session_state.user is None:
    show_login_page()
else:
    show_main_app()
