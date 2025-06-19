import streamlit as st
import pandas as pd
import yfinance as yf
import requests, re

# --- Page Configuration ---
st.set_page_config(page_title="AlphaStack | Valuation", layout="wide")
st.title("📊 AlphaStack: Multi‑Model Valuation Generator")
st.markdown("Choose your valuation model or upload your own numbers.")

# --- Currency Formatter ---
def format_currency(val):
    try:
        val = float(val)
        if val >= 1_00_00_00_000:
            return f"₹{val / 1_00_00_00_000:.2f}T"
        elif val >= 1_00_00_000:
            return f"₹{val / 1_00_00_000:.2f}B"
        elif val >= 1_00_000:
            return f"₹{val / 1_00_000:.2f}M"
        else:
            return f"₹{val:,.2f}"
    except:
        return "N/A"

# --- Fallback Peers ---
FALLBACK = {
    "TCS.NS": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "BRITANNIA.NS": ["NESTLEIND.NS", "HINDUNILVR.NS", "ITC.NS"],
    "RELIANCE.NS": ["IOC.NS", "ONGC.NS", "BPCL.NS"],
    "HDFCBANK.NS": ["ICICIBANK.NS", "AXISBANK.NS", "SBIN.NS"]
}

@st.cache_data(ttl=3600)
def get_peers(ticker):
    try:
        r = requests.get(f"https://finance.yahoo.com/quote/{ticker}/", headers={"User-Agent": "Mozilla/5.0"})
        syms = re.findall(r'"symbol":"([A-Z.]+)"', r.text)
        peers = [s for s in syms if s != ticker and "." in s][:5]
        return peers if peers else FALLBACK.get(ticker.upper(), [])
    except:
        return FALLBACK.get(ticker.upper(), [])

# --- Sidebar ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.selectbox("Stress Test Event", ["None", "COVID‑19 (2020)", "2008 Financial Crisis", "Great Depression", "Scam 1992"])

# --- Ticker Input ---
ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS)", value="TCS.NS")

# --- Upload File ---
st.subheader("📂 Upload Your Financials (Optional override)")
uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"])

# --- Sample File & Download ---
with st.expander("📘 Sample Template"):
    sample_df = pd.DataFrame({
        "Year": [2020, 2021, 2022, 2023, 2024],
        "Revenue": [10000, 11000, 12100, 13500, 15000],
        "EBIT": [2000, 2200, 2500, 2700, 3000],
        "Net Income": [1500, 1600, 1800, 2000, 2200],
        "CapEx": [500, 600, 650, 700, 800],
        "Depreciation": [300, 320, 350, 370, 400],
        "ΔWC": [-200, -150, -100, -50, 0],
        "Cash": [2000, 2200, 2400, 2600, 2800],
        "Debt": [1000, 1100, 1200, 1300, 1400],
        "Shares": [100, 100, 100, 100, 100],
    })
    st.dataframe(sample_df)
    st.download_button("📥 Download Sample Template", data=sample_df.to_csv(index=False), file_name="sample_template.csv")

# --- Sliders for Assumptions ---
st.subheader("🔧 Assumptions (Sliders)")
col1, col2, col3 = st.columns(3)
with col1:
    revenue_growth = st.slider("Revenue Growth (% p.a.)", 0.0, 30.0, 10.0)
    terminal_growth = st.slider("Terminal Growth Rate (%)", 0.0, 10.0, 3.0)
with col2:
    ebit_margin = st.slider("EBIT Margin (%)", 0.0, 50.0, 20.0)
    tax_rate = st.slider("Tax Rate (% of EBIT)", 0.0, 50.0, 25.0)
with col3:
    discount_rate = st.slider("Discount Rate (WACC %)", 0.0, 30.0, 10.0)
    forecast_years = st.slider("Forecast Period (Years)", 1, 10, 5)

# --- Financial Extraction ---
try:
    if uploaded:
        df = pd.read_csv(uploaded) if uploaded.name.endswith("csv") else pd.read_excel(uploaded)
        df = df.sort_values("Year")
        latest = df.iloc[-1]
        revenue = float(latest["Revenue"])
        ebit = float(latest["EBIT"])
        capex = float(latest["CapEx"])
        dep = float(latest["Depreciation"])
        wc = float(latest["ΔWC"])
        cash = float(latest["Cash"])
        debt = float(latest["Debt"])
        shares = float(latest["Shares"])
    else:
        info = yf.Ticker(ticker).info
        revenue = info.get("totalRevenue", 10000000000)
        ebit = revenue * (ebit_margin / 100)
        capex = 100000000
        dep = 50000000
        wc = -20000000
        cash = info.get("totalCash", 1000000000)
        debt = info.get("totalDebt", 500000000)
        shares = info.get("sharesOutstanding", 1000000000)
except:
    st.error("Invalid financials uploaded or not available.")
    st.stop()

# --- DCF ---
tax = ebit * (tax_rate / 100)
nopat = ebit - tax
fcf = nopat + dep - capex - wc

cf_list = []
for year in range(1, forecast_years + 1):
    fcf_proj = fcf * ((1 + revenue_growth / 100) ** year)
    disc = fcf_proj / ((1 + discount_rate / 100) ** year)
    cf_list.append(disc)
terminal_value = (fcf_proj * (1 + terminal_growth / 100)) / ((discount_rate / 100) - (terminal_growth / 100))
terminal_disc = terminal_value / ((1 + discount_rate / 100) ** forecast_years)

enterprise_value = sum(cf_list) + terminal_disc
equity_value = enterprise_value + cash - debt
intrinsic_value = equity_value / shares

# --- Display ---
st.subheader("💰 Valuation Summary")
st.success(f"Enterprise Value: {format_currency(enterprise_value)}")
st.success(f"Equity Value: {format_currency(equity_value)}")
st.success(f"Intrinsic Value per Share: {format_currency(intrinsic_value)}")

# --- Peers ---
st.subheader("📊 Peer Group (Fallback)")
peers = get_peers(ticker.upper())
st.write(", ".join(peers) if peers else "No peers detected.")

# --- Stress Test ---
if stress_event != "None":
    st.subheader("🧨 Stress Test")
    stress_dates = {
        "COVID‑19 (2020)": ("2020-02-15", "2020-03-23"),
        "2008 Financial Crisis": ("2008-09-01", "2008-10-15"),
        "Great Depression": ("1929-09-01", "1930-06-01"),
        "Scam 1992": ("1992-04-01", "1992-05-15"),
    }
    try:
        start, end = stress_dates[stress_event]
        df_crash = yf.download(ticker, start=start, end=end)
        start_price = df_crash["Close"].iloc[0]
        end_price = df_crash["Close"].iloc[-1]
        pct_drop = ((end_price - start_price) / start_price) * 100
        st.warning(f"During {stress_event}, the stock fell {pct_drop:.2f}%.")
    except:
        st.error("Could not retrieve stress test data.")






