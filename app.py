import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
from PIL import Image

st.set_page_config(
    page_title="Cardly • Sports Card Analyzer",
    page_icon="🏈",
    layout="wide"
)

st.title("🏈 Cardly")
st.caption("Upload photos • Track value & rarity • Portfolio tracking")

# Portfolio storage
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=[
        'card_name', 'set', 'year', 'parallel', 'grade', 'purchase_price',
        'est_value', 'rarity', 'link', 'date_added'
    ])

def calculate_estimated_value(row):
    base = {'2024 Panini Prizm': 45, '2024 Donruss Optic': 35, '2024 Panini Mosaic': 30}.get(row['set'], 25)
    mult = {'Prizm': 1.6, 'Silver Prizm': 2.1, 'Mosaic': 1.3, 'Base': 1.0}.get(row.get('parallel', 'Base'), 1.0)
    return round(max(base * mult * (row['grade'] / 10) ** 1.8, 5), 2)

def rarity_score(row):
    score = 40
    if 'rookie' in str(row.get('card_name', '')).lower(): score += 25
    if row.get('grade', 0) >= 9.5: score += 15
    if 'Prizm' in str(row.get('parallel', '')) or 'Silver' in str(row.get('parallel', '')): score += 12
    if row.get('year', 0) >= 2024: score += 8
    return min(int(score), 100)

def get_sportscardspro_link(card_name, set_name, parallel):
    query = f"{card_name} {set_name} {parallel}".strip()
    return f"https://www.sportscardspro.com/search?q={urllib.parse.quote(query)}"

# ==================== ADD CARD ====================
st.subheader("📸 Add New Card")

uploaded_file = st.file_uploader("Upload or take a photo of the card", type=["jpg", "jpeg", "png"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Card", use_column_width=True)

with st.form("add_card_form", clear_on_submit=True):
    st.write("**Card Details** (edit if needed)")

    col1, col2 = st.columns(2)
    with col1:
        card_name = st.text_input("Card Name", value="", placeholder="e.g. Caleb Williams Rookie")
        set_name = st.text_input("Set", value="", placeholder="e.g. 2024 Panini Prizm")
        year = st.number_input("Year", value=2024, min_value=1980, max_value=2026)
    with col2:
        parallel = st.text_input("Parallel", value="Base", placeholder="e.g. Base, Prizm, Silver")
        grade = st.number_input("Grade", value=9.5, min_value=1.0, max_value=10.0, step=0.5)
        purchase_price = st.number_input("Purchase Price ($)", value=0.0, min_value=0.0)

    submitted = st.form_submit_button("✅ Add to Portfolio", use_container_width=True)

    if submitted:
        if not card_name.strip():
            st.error("Please enter a Card Name")
        else:
            new_row = {
                'card_name': card_name.strip(),
                'set': set_name.strip() if set_name else "Unknown Set",
                'year': year,
                'parallel': parallel.strip() if parallel else "Base",
                'grade': grade,
                'purchase_price': purchase_price,
                'est_value': 0,
                'rarity': 0,
                'link': '',
                'date_added': datetime.now().strftime("%Y-%m-%d")
            }
            new_row['est_value'] = calculate_estimated_value(new_row)
            new_row['rarity'] = rarity_score(new_row)
            new_row['link'] = get_sportscardspro_link(new_row['card_name'], new_row['set'], new_row['parallel'])

            st.session_state.portfolio = pd.concat(
                [st.session_state.portfolio, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success(f"✅ Added **{card_name}** to your portfolio!")

# ==================== PORTFOLIO ====================
st.subheader("📋 Your Portfolio")

if len(st.session_state.portfolio) > 0:
    df = st.session_state.portfolio.copy()

    total_value = df['est_value'].sum()
    total_cost = df['purchase_price'].sum()
    gain = total_value - total_cost
    gain_pct = (gain / total_cost * 100) if total_cost > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cards", len(df))
    col2.metric("Portfolio Value", f"${total_value:,.2f}")
    col3.metric("Total Invested", f"${total_cost:,.2f}")
    col4.metric("Unrealized Gain", f"${gain:,.2f}", f"{gain_pct:+.1f}%")

    st.dataframe(
        df[['card_name', 'set', 'parallel', 'grade', 'est_value', 'rarity', 'link']],
        column_config={
            "link": st.column_config.LinkColumn("SportsCardsPro", display_text="🔗 View"),
            "est_value": st.column_config.NumberColumn("Est. Value", format="$%.2f"),
            "rarity": st.column_config.ProgressColumn("Rarity", min_value=0, max_value=100)
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No cards yet. Upload a photo and fill in the details above to get started.")

st.caption("Cardly • Public Beta")
