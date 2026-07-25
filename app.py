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

# ---------- SUPABASE CONNECTION ----------
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
        "purchase_price", "beckett", "ebay_sold", "ebay_active", "date_added"
    ])

# ---------- HELPER FUNCTIONS ----------
def make_links(card_name, set_name, year, parallel):
    query = f"{year} {set_name} {card_name} {parallel} PSA BGS".strip()
    query = re.sub(r'\s+', ' ', query)
    encoded = urllib.parse.quote(query)

    ebay_sold = f"https://www.ebay.com/sch/i.html?_nkw={encoded}&LH_Sold=1&LH_Complete=1"
    ebay_active = f"https://www.ebay.com/sch/i.html?_nkw={encoded}"

    slug = f"{year}-{set_name}".lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    beckett = f"https://www.beckett.com/news/{slug}-cards/"

    return beckett, ebay_sold, ebay_active

def load_user_portfolio(user_id: str):
    try:
        res = supabase.table("portfolios").select("cards").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            cards = res.data[0]["cards"]
            if cards:
                return pd.DataFrame(cards)
        return pd.DataFrame(columns=[
            "card_name", "set", "year", "parallel", "grade",
            "purchase_price", "beckett", "ebay_sold", "ebay_active", "date_added"
        ])
    except Exception as e:
        st.error(f"Error loading portfolio: {e}")
        return pd.DataFrame(columns=[
            "card_name", "set", "year", "parallel", "grade",
            "purchase_price", "beckett", "ebay_sold", "ebay_active", "date_added"
        ])

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

# ---------- AUTHENTICATION ----------
def show_login_page():
    st.title("🏈 Cardly")
    st.caption("Sign in to save and manage your sports card portfolio")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)

            if submit:
                try:
                    res = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    st.session_state.user = res.user
                    st.session_state.portfolio = load_user_portfolio(res.user.id)
                    st.success("Logged in successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with tab2:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            submit = st.form_submit_button("Create Account", use_container_width=True)

            if submit:
                try:
                    res = supabase.auth.sign_up({
                        "email": email,
                        "password": password
                    })
                    st.success("Account created! Please check your email to confirm, then log in.")
                except Exception as e:
                    st.error(f"Sign up failed: {e}")

# ---------- MAIN APP (ONLY SHOWN WHEN LOGGED IN) ----------
def show_main_app():
    st.title("🏈 Cardly")
    st.caption(f"Logged in as {st.session_state.user.email}")

    if st.button("Log out"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.portfolio = pd.DataFrame()
        st.rerun()

    st.divider()

    # ----- ADD CARD -----
    st.subheader("📸 Add New Card")

    uploaded = st.file_uploader("Upload or take a photo of the card", type=["jpg", "jpeg", "png"])

    if uploaded is not None:
        image = Image.open(uploaded).convert("RGB")
        st.image(image, caption="Uploaded Card", use_container_width=True)

    with st.form("add_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            card_name = st.text_input("Card Name")
            set_name = st.text_input("Set")
            year = st.number_input("Year", value=2024, min_value=1980, max_value=2026)
        with c2:
            parallel = st.text_input("Parallel", value="Base")
            grade = st.number_input("Grade", value=9.5, min_value=1.0, max_value=10.0, step=0.5)
            price = st.number_input("Purchase Price ($)", value=0.0, min_value=0.0)

        submitted = st.form_submit_button("Add to Portfolio", use_container_width=True)

        if submitted:
            if not card_name.strip():
                st.error("Please enter a Card Name")
            else:
                beckett, ebay_sold, ebay_active = make_links(
                    card_name, set_name, year, parallel
                )

                new_row = {
                    "card_name": card_name.strip(),
                    "set": set_name.strip() if set_name else "Unknown Set",
                    "year": year,
                    "parallel": parallel.strip() if parallel else "Base",
                    "grade": grade,
                    "purchase_price": price,
                    "beckett": beckett,
                    "ebay_sold": ebay_sold,
                    "ebay_active": ebay_active,
                    "date_added": datetime.now().strftime("%Y-%m-%d")
                }

                st.session_state.portfolio = pd.concat(
                    [st.session_state.portfolio, pd.DataFrame([new_row])],
                    ignore_index=True
                )
                save_user_portfolio(st.session_state.user.id, st.session_state.portfolio)
                st.success(f"Added {card_name}")

    # ----- PORTFOLIO -----
    st.subheader("Your Portfolio")

    df = st.session_state.portfolio

    if len(df) > 0:
        total_cost = df["purchase_price"].sum()

        m1, m2 = st.columns(2)
        m1.metric("Cards", len(df))
        m2.metric("Total Invested", f"${total_cost:,.2f}")

        st.dataframe(
            df[[
                "card_name", "set", "parallel", "grade",
                "purchase_price", "beckett", "ebay_sold", "ebay_active"
            ]],
            column_config={
                "beckett": st.column_config.LinkColumn("Beckett", display_text="Beckett"),
                "ebay_sold": st.column_config.LinkColumn("eBay Sold (Graded)", display_text="Sold"),
                "ebay_active": st.column_config.LinkColumn("eBay Active", display_text="Active"),
                "purchase_price": st.column_config.NumberColumn("Cost", format="$%.2f")
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

# ---------- APP ROUTING ----------
if st.session_state.user is None:
    show_login_page()
else:
    show_main_app()
