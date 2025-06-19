# Prepare the updated code with:
# - Stress Test functionality
# - AI-generated insight summary
# - Full working Streamlit app

updated_code = """
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
import requests, re

# --- Page Configuration ---
st.set_page_config(page_title="AlphaStack | Valuation", layout="wide")
st.title("📊 AlphaStack: Multi‑Model Valuation Generator")
st.markdown("Choose your valuation model or upload your own numbers.")

# --- Format Helper ---
def format_currency(val):
    try:
        val = float(val)
        if val >= 1_00_00_00_000:
            return f"₹{val/1_00_00_00_000:.2f}T"
        elif val >= 1_00_00_000:
            return f"₹{val/1_00_00_000:.2f}B"
        elif val >= 1_00_000:
            return f"₹{val/1_00_000:.2f}M"
        else:
            return f"₹{val:,.2f}"
    except:
        return "N/A"

# --- Fallback Peer DB ---
FALLBACK = {
    "TCS.NS": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "BRITANNIA.NS": ["NESTLEIND.NS", "HINDUNILVR.NS", "ITC.NS"],
    "RELIANCE.NS": ["IOC.NS", "ONGC.NS", "BPCL.NS"],
    "HDFCBANK.NS": ["ICICIBANK.NS", "AXISBANK.NS", "SBIN.NS"]
}

# --- Peer Detection via Yahoo ---
@st.cache_data(ttl=3600)
def get_yahoo_peers(ticker):
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        syms = re.findall(r'"symbol":"([A-Z\\.]+)"', r.text)
        peers = []
        for s in syms:
            if s != ticker and "." in s and s not in peers:
                peers.append(s)
            if len(peers) >= 5:
                break
        return peers
    except:
        return []

# --- Sidebar Settings ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.selectbox("Stress Test Event", [
    "None", "COVID‑19 (2020)", "2008 Financial Crisis", "Great Depression", "Scam 1992"
])
ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS)", value="TCS.NS")

# --- Upload File ---
st.subheader("📂 Upload Your Financials (Optional override)")
uploaded = st.file_uploader("CSV/Excel with columns: Year, Revenue, EBIT, Net Income, CapEx, Depreciation, ΔWC, Cash, Debt, Shares", type=["csv", "xlsx"])

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

# --- Extract Financials or Use Defaults ---
if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith("csv") else pd.read_excel(uploaded)
    df = df.sort_values("Year")
    yrs = df["Year"].iloc[-1] - df["Year"].iloc[0]
    rev_growth = ((df["Revenue"].iloc[-1] / df["Revenue"].iloc[0]) ** (1 / yrs) - 1) * 100
    ebit_margin = (df["EBIT"] / df["Revenue"]).mean() * 100
    capex_pct = (df["CapEx"] / df["Revenue"]).mean() * 100
    dep_pct = (df["Depreciation"] / df["Revenue"]).mean() * 100
    wc_pct = (df["ΔWC"] / df["Revenue"]).mean() * 100
    revenue = df["Revenue"].iloc[-1]
    cash = df["Cash"].iloc[-1]
    debt = df["Debt"].iloc[-1]
    shares = df["Shares"].iloc[-1]
else:
    rev_growth = 10.0
    ebit_margin = 20.0
    capex_pct = 5.0
    dep_pct = 3.0
    wc_pct = -2.0
    revenue = 1000
    cash = 200
    debt = 100
    shares = 50

# --- Sliders ---
st.header("🔧 Assumptions (Sliders)")
col1, col2 = st.columns(2)
with col1:
    revenue_growth = st.slider("Revenue Growth (% p.a.)", 0.0, 30.0, float(rev_growth), step=0.1)
    ebit_margin = st.slider("EBIT Margin (%)", 0.0, 50.0, float(ebit_margin), step=0.1)
    terminal_growth = st.slider("Terminal Growth Rate (%)", 0.0, 10.0, 3.0)
with col2:
    tax_rate = st.slider("Tax Rate (% of EBIT)", 0.0, 50.0, 25.0)
    discount_rate = st.slider("Discount Rate (WACC %)", 0.0, 30.0, 10.0)
    forecast_years = st.slider("Forecast Period (Years)", 1, 10, 5)

# --- Valuation ---
if st.button("🚀 Generate Valuation"):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")
        price = hist["Close"].iloc[-1]

        ebit = revenue * (ebit_margin / 100)
        tax = ebit * (tax_rate / 100)
        nopat = ebit - tax
        dep = revenue * (dep_pct / 100)
        capex = revenue * (capex_pct / 100)
        wc = revenue * (wc_pct / 100)
        base_fcf = nopat + dep - capex - wc

        projections = []
        for year in range(1, forecast_years + 1):
            fcf = base_fcf * ((1 + revenue_growth / 100) ** year)
            disc = fcf / ((1 + discount_rate / 100) ** year)
            projections.append((year, round(fcf, 2), round(disc, 2)))

        df_proj = pd.DataFrame(projections, columns=["Year", "Projected FCF", "Discounted FCF"])
        st.markdown("### 🔢 DCF Cash Flows")
        st.dataframe(df_proj)

        terminal_val = (projections[-1][1] * (1 + terminal_growth / 100)) / ((discount_rate / 100) - (terminal_growth / 100))
        disc_terminal = terminal_val / ((1 + discount_rate / 100) ** forecast_years)
        ev = sum(df_proj["Discounted FCF"]) + disc_terminal
        eq_val = ev + cash - debt
        iv = eq_val / shares

        st.markdown("### 💰 Valuation Summary")
        st.success(f"Enterprise Value: {format_currency(ev)}")
        st.success(f"Equity Value: {format_currency(eq_val)}")
        st.success(f"Intrinsic Value per Share: {format_currency(iv)}")

        diff_pct = (iv - price) / price * 100
        st.info(f"🧠 Insight: {'Undervalued' if diff_pct > 0 else 'Overvalued'} by {abs(diff_pct):.2f}% (Market: ₹{price:.2f} vs IV: ₹{iv:.2f})")

        # Chart
        st.markdown("### 📉 1Y Stock Price Chart")
        fig = go.Figure([go.Scatter(x=hist.index, y=hist["Close"], mode='lines', name="Price")])
        fig.update_layout(title=f"{ticker} Price Trend", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)

        # Peers
        st.markdown("### 🥊 Peer Comparison")
        peers = get_yahoo_peers(ticker) or FALLBACK.get(ticker.upper(), [])
        if peers:
            comp_data = []
            for peer in peers:
                pinfo = yf.Ticker(peer).info
                comp_data.append({
                    "Ticker": peer,
                    "P/E": pinfo.get("trailingPE"),
                    "Market Cap": format_currency(pinfo.get("marketCap")),
                    "Revenue Growth (%)": round(pinfo.get("revenueGrowth", 0) * 100, 2) if pinfo.get("revenueGrowth") else "N/A"
                })
            st.dataframe(pd.DataFrame(comp_data))
        else:
            st.warning("No peer data found.")

        # --- Stress Test ---
        if stress_event != "None":
            stress_events = {
                "COVID‑19 (2020)": ("2020-02-15", "2020-03-23"),
                "2008 Financial Crisis": ("2008-09-01", "2008-10-15"),
                "Great Depression": ("1929-09-01", "1930-06-01"),
                "Scam 1992": ("1992-04-01", "1992-05-15"),
            }
            start, end = stress_events[stress_event]
            crisis_df = yf.download(ticker, start=start, end=end)
            if not crisis_df.empty:
                start_price = float(crisis_df["Close"].iloc[0])
                end_price = float(crisis_df["Close"].iloc[-1])
                pct_drop = ((end_price - start_price) / start_price) * 100
                new_price = price * (1 + pct_drop / 100)
                st.markdown("### 🧨 Stress Test")
                st.warning(f"During **{stress_event}**, this stock dropped **{pct_drop:.2f}%**.")
                st.info(f"If repeated today: ₹{price:.2f} → ₹{new_price:.2f}")
            else:
                st.error("No data available for this event.")

    except Exception as e:
        st.error(f"Something went wrong: {e}")
"""

updated_code[:3000]  # Output the first part for verification.






