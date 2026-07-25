import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
from PIL import Image
import requests
import base64
import io
import re

st.set_page_config(
    page_title="Cardly • Sports Card Analyzer",
    page_icon="🏈",
    layout="centered"
)

st.title("🏈 Cardly")
st.caption("Upload photos • AI reads the card • Track your portfolio")

# Portfolio storage
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=[
        "card_name", "set", "year", "parallel", "grade", "purchase_price",
        "est_value", "rarity", "link", "date_added"
    ])

def get_ocr_space_text(image):
    try:
        api_key = st.secrets["OCR_SPACE_API_KEY"]
    except Exception:
        st.error("OCR.space API key not found in Secrets.")
        return []

    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

    payload = {
        "apikey": api_key,
        "base64Image": f"data:image/jpeg;base64,{img_base64}",
        "language": "eng",
        "isOverlayRequired": False,
        "OCREngine": 2
    }

    try:
        response = requests.post("https://api.ocr.space/parse/image", data=payload, timeout=30)
        result = response.json()

        if result.get("IsErroredOnProcessing"):
            st.warning("OCR failed: " + str(result.get("ErrorMessage", ["Unknown error"])))
            return []

        parsed = result.get("ParsedResults", [])
        if parsed:
            text = parsed[0].get("ParsedText", "")
            return [line.strip() for line in text.split("\n") if line.strip()]
        return []
    except Exception as e:
        st.warning(f"OCR request failed: {e}")
        return []

def analyze_card_text(texts):
    full_text = " ".join(texts).lower()
    card_name = ""
    set_name = ""
    year = 2024
    parallel = "Base"

    year_match = re.search(r"\b(202[0-6])\b", full_text)
    if year_match:
        year = int(year_match.group(1))

    set_keywords = {
        "prizm": "Panini Prizm",
        "optic": "Donruss Optic",
        "mosaic": "Panini Mosaic",
        "select": "Panini Select",
        "donruss": "Donruss",
        "topps": "Topps",
        "chrome": "Topps Chrome",
        "bowman": "Bowman"
    }

    for key, value in set_keywords.items():
        if key in full_text:
            set_name = f"{year} {value}"
            break

    parallel_keywords = ["silver", "gold", "prizm", "holo", "refractor", "green", "blue", "red"]
    for p in parallel_keywords:
        if p in full_text:
            parallel = p.title()
            break

    ignore = {"panini", "prizm", "optic", "mosaic", "select", "donruss", "topps", "the", "of", "and", "rookie", "rc", "card"}
    candidates = [t.strip() for t in texts if len(t.strip()) > 5 and not any(w in t.lower() for w in ignore)]
    if candidates:
        card_name = sorted(candidates, key=len, reverse=True)[0]

    if ("rookie" in full_text or "rc" in full_text) and card_name and "rookie" not in card_name.lower():
        card_name += " Rookie"

    return {
        "card_name": card_name,
        "set": set_name,
        "year": year,
        "parallel": parallel,
        "raw_text": texts
    }

def calculate_estimated_value(row):
    base = {"2024 Panini Prizm": 45, "2024 Donruss Optic": 35, "2024 Panini Mosaic": 30}.get(row["set"], 25)
    mult = {"Prizm": 1.6, "Silver": 2.1, "Gold": 2.5, "Base": 1.0}.get(row.get("parallel", "Base"), 1.0)
    return round(max(base * mult * (row["grade"] / 10) ** 1.8, 5), 2)

def rarity_score(row):
    score = 40
    if "rookie" in str(row.get("card_name", "")).lower():
        score += 25
    if row.get("grade", 0) >= 9.5:
        score += 15
    if any(x in str(row.get("parallel", "")).lower() for x in ["prizm", "silver", "gold"]):
        score += 12
    if row.get("year", 0) >= 2024:
        score += 8
    return min(int(score), 100)

def get_beckett_link(set_name, year):
    query = f"{year} {set_name}".strip()
    return f"https://www.beckett.com/search?q={urllib.parse.quote(query)}"

# ==================== ADD CARD ====================
st.subheader("📸 Add New Card")

uploaded_file = st.file_uploader("Upload or take a photo of the card", type=["jpg", "jpeg", "png"])

analysis = None

if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="Uploaded Card", use_container_width=True)

    with st.spinner("Reading card with OCR.space..."):
        texts = get_ocr_space_text(image)
        if texts:
            analysis = analyze_card_text(texts)

    if analysis and analysis.get("raw_text"):
        with st.expander("Raw text detected by AI"):
