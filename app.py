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
            st.write(analysis["raw_text"])

with st.form("add_card_form", clear_on_submit=True):
    st.write("**Card Details** (AI suggestions — edit if needed)")

    col1, col2 = st.columns(2)
    with col1:
        card_name = st.text_input("Card Name", value=analysis["card_name"] if analysis else "", placeholder="e.g. Caleb Williams Rookie")
        set_name = st.text_input("Set", value=analysis["set"] if analysis else "", placeholder="e.g. 2024 Panini Prizm")
        year = st.number_input("Year", value=analysis["year"] if analysis else 2024, min_value=1980, max_value=2026)
    with col2:
        parallel = st.text_input("Parallel", value=analysis["parallel"] if analysis else "Base", placeholder="e.g. Base, Silver")
        grade = st.number_input("Grade", value=9.5, min_value=1.0, max_value=10.0, step=0.5)
        purchase_price = st.number_input("Purchase Price ($)", value=0.0, min_value=0.0)

    submitted = st.form_submit_button("Add to Portfolio", use_container_width=True)

    if submitted:
        if not card_name.strip():
            st.error("Please enter a Card Name")
        else:
            new_row = {
                "card_name": card_name.strip(),
                "set": set_name.strip() if set_name else "Unknown Set",
                "year": year,
                "parallel": parallel.strip() if parallel else "Base",
                "grade": grade,
                "purchase_price": purchase_price,
                "est_value": 0,
                "rarity": 0,
                "link": "",
                "date_added": datetime.now().strftime("%Y-%m-%d")
            }
            new_row["est_value"] = calculate_estimated_value(new_row)
            new_row["rarity"] = rarity_score(new_row)
            new_row["link"] = get_beckett_link(new_row["set"], new_row["year"])

            st.session_state.portfolio = pd.concat(
                [st.session_state.portfolio, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success(f"Added **{card_name}** to your portfolio!")

# ==================== PORTFOLIO ====================
st.subheader("Your Portfolio")

if len(st.session_state.portfolio) > 0:
    df = st.session_state.portfolio

    total_value = df["est_value"].sum()
    total_cost = df["purchase_price"].sum()
    gain = total_value - total_cost
    gain_pct = (gain / total_cost * 100) if total_cost > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cards", len(df))
    c2.metric("Portfolio Value", f"${total_value:,.2f}")
    c3.metric("Total Invested", f"${total_cost:,.2f}")
    c4.metric("Unrealized Gain", f"${gain:,.2f}", f"{gain_pct:+.1f}%")

    st.dataframe(
        df[["card_name", "set", "parallel", "grade", "est_value", "rarity", "link"]],
        column_config={
            "link": st.column_config.LinkColumn("Beckett", display_text="View on Beckett"),
            "est_value": st.column_config.NumberColumn("Est. Value", format="$%.2f"),
            "rarity": st.column_config.ProgressColumn("Rarity", min_value=0, max_value=100)
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No cards yet. Upload a photo above to get started.")

st.caption("Cardly • Public Beta • OCR powered by OCR.space")
