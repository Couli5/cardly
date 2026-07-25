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
    layout="wide"
)

st.title("🏈 Cardly")
st.caption("Upload photos • AI reads the card • Track your portfolio")

# Portfolio storage
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=[
        'card_name', 'set', 'year', 'parallel', 'grade', 'purchase_price',
        'est_value', 'rarity', 'link', 'date_added'
    ])

def get_ocr_space_text(image):
    """Send image to OCR.space and return extracted text"""
    try:
        api_key = st.secrets["OCR_SPACE_API_KEY"]
    except:
        st.error("OCR.space API key not found. Please add it in Streamlit Secrets.")
        return []

    # Convert image to base64
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

    payload = {
        'apikey': api_key,
        'base64Image': f'data:image/jpeg;base64,{img_base64}',
        'language': 'eng',
        'isOverlayRequired': False,
        'OCREngine': 2
    }

    try:
        response = requests.post('https://api.ocr.space/parse/image', data=payload, timeout=30)
        result = response.json()

        if result.get('IsErroredOnProcessing'):
            st.warning("OCR failed: " + str(result.get('ErrorMessage', 'Unknown error')))
            return []

        parsed_results = result.get('ParsedResults', [])
        if parsed_results:
            text = parsed_results[0].get('ParsedText', '')
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return lines
        return []
    except Exception as e:
        st.warning(f"OCR request failed: {e}")
        return []

def analyze_card_text(texts):
    """Try to extract useful card info from OCR text"""
    full_text = " ".join(texts).lower()
    original_texts = texts

    card_name = ""
    set_name = ""
    year = 2024
    parallel = "Base"

    # Find year
    year_match = re.search(r'\b(202[0-6])\b', full_text)
    if year_match:
        year = int(year_match.group(1))

    # Common set keywords
    set_keywords = {
        'prizm': 'Panini Prizm',
        'optic': 'Donruss Optic',
        'mosaic': 'Panini Mosaic',
        'select': 'Panini Select',
        'donruss': 'Donruss',
        'chronicles': 'Panini Chronicles',
        'absolute': 'Panini Absolute',
        'prestige': 'Panini Prestige',
        'score': 'Score',
        'topps': 'Topps',
        'bowman': 'Bowman',
        'chrome': 'Topps Chrome'
    }

    for key, value in set_keywords.items():
        if key in full_text:
            set_name = f"{year} {value}"
            break

    # Parallel keywords
    parallel_keywords = ['silver', 'gold', 'prizm', 'holo', 'refractor', 'mojo', 'pulsar', 'disco', 'hyper', 'wave', 'green', 'blue', 'red']
