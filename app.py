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

# Force clean portfolio columns
correct_columns = [
    "card_name", "set", "year", "parallel", "grade",
    "purchase_price", "est_value", "rarity",
    "beckett", "ebay_sold", "ebay_active", "date_added"
]

if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=correct_columns)
else:
    # Reset if columns don't match (prevents blank page)
    if list(st.session_state.portfolio.columns) != correct_columns:
        st.session_state.portfolio = pd.DataFrame(columns=correct_columns)

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

    return min(score, 100)

def make_links(card_name, set_name, year, parallel):
    query = f"{year} {set_name} {card_name} {parallel}".strip()
    query = re.sub(r'\s+', ' ', query)
    encoded = urllib.parse.quote(query)

    ebay_sold = f"https://www.ebay.com/sch/i.html?_nkw={encoded}&LH_Sold=1&LH_Complete=1"
    ebay_active = f"https://www.ebay.com/sch/i.html?_nkw={encoded}"

    slug = f"{year}-{set_name}".lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    beckett = f"https://www.beckett.com/news/{slug}-cards/"

    return beckett, ebay_sold, ebay_active

# ========== ADD CARD ==========
st.subheader("📸 Add New Card")

uploaded = st.file_uploader(
    "Upload or take a photo of the card",
    type=["jpg", "jpeg", "png"]
)

analysis = None

if uploaded is not None:
    try:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, caption="Uploaded Card", use_container_width=True)

        with st.spinner("Reading card with OCR.space..."):
            texts = get_ocr_space_text(image)
            if texts:
                analysis = analyze_card_text(texts)

        if analysis and analysis.get("raw_text"):
            with st.expander("Raw text detected by AI"):
                st.write(analysis["raw_text"])
    except Exception as e:
        st.error(f"Error reading image: {e}")

with st.form("add_form", clear_on_submit=True):
    st.write("**Card Details**")

    c1, c2 = st.columns(2)

    with c1:
        default_name = analysis["card_name"] if analysis else ""
        card_name = st.text_input("Card Name", value=default_name)

        default_set = analysis["set"] if analysis else ""
        set_name = st.text_input("Set", value=default_set)

        default_year = analysis["year"] if analysis else 2024
        year = st.number_input("Year", value=default_year, min_value=1980, max_value=2026)

    with c2:
        default_par = analysis["parallel"] if analysis else "Base"
        parallel = st.text_input("Parallel", value=default_par)

        grade = st.number_input("Grade", value=9.5, min_value=1.0, max_value=10.0, step=0.5)
        price = st.number_input("Purchase Price ($)", value=0.0, min_value=0.0)

    submitted = st.form_submit_button("Add to Portfolio", use_container_width=True)

    if submitted:
        if not card_name.strip():
            st.error("Please enter a Card Name")
        else:
            row = {
                "card_name": card_name.strip(),
                "set": set_name.strip() if set_name else "Unknown Set",
                "year": year,
                "parallel": parallel.strip() if parallel else "Base",
                "grade": grade,
                "purchase_price": price,
                "est_value": 0,
                "rarity": 0,
                "beckett": "",
                "ebay_sold": "",
                "ebay_active": "",
                "date_added": datetime.now().strftime("%Y-%m-%d")
            }

            row["est_value"] = calculate_estimated_value(row)
            row["rarity"] = rarity_score(row)

            beckett, ebay_sold, ebay_active = make_links(
                row["card_name"], row["set"], row["year"], row["parallel"]
            )
            row["beckett"] = beckett
            row["ebay_sold"] = ebay_sold
            row["ebay_active"] = ebay_active

            new_df = pd.DataFrame([row])
            st.session_state.portfolio = pd.concat(
                [st.session_state.portfolio, new_df],
                ignore_index=True
            )
            st.success(f"Added {card_name}")

# ========== PORTFOLIO ==========
st.subheader("Your Portfolio")

df = st.session_state.portfolio

if len(df) > 0:
    total_value = df["est_value"].sum()
    total_cost = df["purchase_price"].sum()
    gain = total_value - total_cost
    gain_pct = (gain / total_cost * 100) if total_cost > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cards", len(df))
    m2.metric("Value", f"${total_value:,.2f}")
    m3.metric("Invested", f"${total_cost:,.2f}")
    m4.metric("Gain", f"${gain:,.2f}", f"{gain_pct:+.1f}%")

    st.dataframe(
        df[[
            "card_name", "set", "parallel", "grade",
            "est_value", "rarity", "beckett", "ebay_sold", "ebay_active"
        ]],
        column_config={
            "beckett": st.column_config.LinkColumn("Beckett", display_text="Beckett"),
            "ebay_sold": st.column_config.LinkColumn("eBay Sold", display_text="Sold"),
            "ebay_active": st.column_config.LinkColumn("eBay Active", display_text="Active"),
            "est_value": st.column_config.NumberColumn("Est. Value", format="$%.2f"),
            "rarity": st.column_config.ProgressColumn("Rarity", min_value=0, max_value=100)
        },
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")
    st.write("**Delete a card**")

    options = []
    for i, row in df.iterrows():
        options.append(f"{i+1}. {row['card_name']} ({row['set']})")

    selected = st.selectbox("Select card to delete", options)

    if st.button("Delete Selected Card", type="primary"):
        idx = int(selected.split(".")[0]) - 1
        st.session_state.portfolio = df.drop(idx).reset_index(drop=True)
        st.success("Card deleted")
        st.rerun()

else:
    st.info("No cards yet. Upload a photo to get started.")

st.caption("Cardly • OCR powered by OCR.space")
