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
        "purchase_price", "est_value", "rarity", "link
