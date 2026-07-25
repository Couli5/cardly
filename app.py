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
    page_title="Cardly",
    page_icon="🏈",
    layout="centered"
)

st.title("🏈 Cardly")
st.caption("Upload photos • AI reads the card • Track portfolio")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=[
        "card_name", "set", "year", "parallel", "grade",
        "purchase_price", "est_value", "rarity",
        "beckett", "ebay_sold", "ebay_active", "date_added"
    ])

def get_ocr_space_text(image):
    try:
        api_key = st.secrets["OCR_SPACE_API_KEY"]
    except Exception:
        st.error("API key not found in Secrets.")
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
        r = requests.post(
            "https://api.ocr.space/parse/image",
            data=payload,
            timeout=30
        )
        result = r.json()

        if result.get("IsErroredOnProcessing"):
            st.warning("OCR failed")
            return []

        parsed = result.get("ParsedResults", [])
        if parsed:
            text = parsed[0].get("ParsedText", "")
            return [x.strip() for x in text.split("\n") if x.strip()]
        return []
    except Exception as e:
        st.warning(f"OCR error: {e}")
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

    ignore = {
        "panini", "prizm", "optic", "mosaic", "select",
        "donruss", "topps", "the", "of", "and", "rookie", "rc", "card"
    }

    candidates = []
    for t in texts:
        clean = t.strip()
        if len(clean) > 5 and not any(w in clean.lower() for w in ignore):
            candidates.append(clean)

    if candidates:
        card_name = sorted(candidates, key=len, reverse=True)[0]

    if ("rookie" in full or "rc" in full) and card_name:
        if "rookie" not in card_name.lower():
            card_name += " Rookie"

    return {
        "card_name": card_name,
        "set": set_name,
        "year": year,
        "parallel": parallel,
        "raw_text": texts
    }

def calculate_estimated_value(row):
    base_map = {
        "2024 Panini Prizm": 45,
        "2024 Donruss Optic": 35,
        "2024 Panini Mosaic": 30
    }
    base = base_map.get(row["set"], 25)

    mult_map = {
        "Prizm": 1.6,
        "Silver": 2.1,
        "Gold": 2.5,
        "Base": 1.0
    }
    mult = mult_map.get(row.get("parallel", "Base"), 1.0)

    value = base * mult * (row["grade"] / 10) ** 1.8
    return round(max(value, 5), 2)

def rarity_score(row):
    score = 40
    name = str(row.get("card_name", "")).lower()
    parallel = str(row.get("parallel", "")).lower()

    if "rookie" in name:
        score += 25
    if row.get("grade", 0) >= 9.5:
        score += 15
    if any(x in parallel for x in ["prizm", "silver", "gold"]):
        score += 12
    if row.get("year", 0) >= 2024:
        score += 8

    return min
