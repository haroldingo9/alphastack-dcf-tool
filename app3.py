import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import plotly.graph_objs as go
import requests
from bs4 import BeautifulSoup
import re

# --- Page Setup ---
st.set_page_config(page_title="AlphaStack | Smart DCF Tool", layout="wide")
st.title("📊 AlphaStack: Advanced DCF & Valuation Tool")
st.markdown("DCF, Peer Comparison, Stress Test, Scenarios, AI Insights")

# --- Peer Detection Function ---
@st.cache_data(ttl=3600)
def get_yahoo_peers(ticker):
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "lxml")
        pattern = re.compile(r'\"symbol\":\"([A-Z\.]+)\"')
        matches = pattern.findall(res.text)
        peers = []
        for match in matches:
            if match != ticker and "." in match and match not in peers:
                peers.append(match)
            if len(peers) >= 5:
                break
        return peers
    except Exception as e:
        return []

# --- Scenario Settings ---
st.sidebar.header("⚙️ Scenario Settings")
scenario_type = st.sidebar.selectbox("Choose Scenario", ["Base", "Bull", "Bear", "Custom"])
risk_profile = st.sidebar.radio("Client Risk Level", ["Low", "Moderate", "High"], horizontal=True)

scenario_data = {
    "Bull": {"revenue_growth": 18, "ebit_margin": 24, "discount_rate": 8.5, "terminal_growth": 4.5},
    "Base": {"revenue_growth": 10, "ebit_margin": 20, "discount_rate": 10, "terminal_growth": 3},
    "Bear": {"revenue_growth": 4, "ebit_margin": 16, "discount_rate": 13, "terminal_growth": 1.5}
}

if scenario_type in scenario_data:
    rev_growth = scenario_data[scenario_type]["revenue_growth"]
    ebit_margin = scenario_data[scenario_type]["ebit_margin"]
    discount_rate = scenario_data[scenario_type]["discount_rate"]
    terminal_growth = scenario_data[scenario_type]["terminal_growth"]
else:
    rev_growth = st.sidebar.number_input("Revenue Growth (%)", value=10.0)
    ebit_margin = st.sidebar.number_input("EBIT Margin (%)", value=20.0)
    discount_rate = st.sidebar.number_input("Discount Rate (%)", value=10.0)
    terminal_growth = st.sidebar.number_input("Terminal Growth Rate (%)", value=3.0)

forecast_years = st.sidebar.slider("Forecast Period (Years)", 3, 10, 5)

# --- Ticker Input ---
ticker = st.text_input("Enter Stock Ticker", "TCS.NS")
stock = yf.Ticker(ticker)

if st.button("🚀 Generate Valuation"):
    try:
        info = stock.info
        st.subheader(f"🏢 Company: {info.get('shortName', ticker)}")
        st.write(f"Sector: {info.get('sector')} | Industry: {info.get('industry')}")
        st.write(f"Market Cap: ₹{info.get('marketCap'):,} | PE: {info.get('trailingPE')} | Dividend Yield: {info.get('dividendYield', 0) * 100:.2f}%")

        revenue = info.get("totalRevenue", 1000)
        ebit = revenue * (ebit_margin / 100)
        tax = ebit * 0.25
        nopat = ebit - tax
        dep = 50
        capex = 100
        wc = -20
        cash = info.get("totalCash", 200)
        debt = info.get("totalDebt", 100)
        shares = info.get("sharesOutstanding", 50)

        fcf = nopat + dep - capex - wc
        cash_flows = []
        for year in range(1, forecast_years + 1):
            fcf_proj = fcf * ((1 + rev_growth / 100) ** year)
            fcf_disc = fcf_proj / ((1 + discount_rate / 100) ** year)
            cash_flows.append((year, round(fcf_proj, 2), round(fcf_disc, 2)))

        df_cf = pd.DataFrame(cash_flows, columns=["Year", "Projected FCF", "Discounted FCF"])
        last_fcf = cash_flows[-1][1]
        terminal_val = (last_fcf * (1 + terminal_growth / 100)) / (discount_rate / 100 - terminal_growth / 100)
        disc_terminal = terminal_val / ((1 + discount_rate / 100) ** forecast_years)

        total_ev = df_cf["Discounted FCF"].sum() + disc_terminal
        equity_val = total_ev + cash - debt
        intrinsic_val = equity_val / shares

        st.markdown("### 🔢 Cash Flow Forecast")
        st.dataframe(df_cf)
        st.success(f"Enterprise Value: ₹{total_ev:,.2f}")
        st.success(f"Equity Value: ₹{equity_val:,.2f}")
        st.success(f"Intrinsic Value per Share: ₹{intrinsic_val:,.2f}")

        # 📉 Stock Chart
        hist = stock.history(period="1y")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], mode='lines', name='Close Price'))
        fig.update_layout(title=f"{ticker} - 1Y Price Chart")
        st.plotly_chart(fig)

        # 🥊 Auto Peer Detection
        st.markdown("### 🥊 Peer Comparison")
        competitors = get_yahoo_peers(ticker)
        comp_data = []
        for peer in competitors:
            try:
                p_info = yf.Ticker(peer).info
                comp_data.append({
                    "Ticker": peer,
                    "PE": p_info.get("trailingPE", None),
                    "Market Cap": p_info.get("marketCap", None),
                    "Growth Rate": p_info.get("revenueGrowth", None),
                })
            except:
                continue
        if comp_data:
            st.dataframe(pd.DataFrame(comp_data))
        else:
            st.info("No peers detected.")

        # 🤖 AI Insight
        st.markdown("### 🤖 AlphaStack Insight")
        current_price = hist["Close"].iloc[-1]
        perc_diff = ((intrinsic_val - current_price) / current_price) * 100
        insight = f"**{ticker.upper()}** appears **{'undervalued' if perc_diff > 0 else 'overvalued'}** by **{abs(perc_diff):.1f}%**. "
        insight += f"Intrinsic value is ₹{intrinsic_val:,.2f} vs market price ₹{current_price:,.2f}."
        st.info(insight)

        # 📄 PDF Placeholder
        st.markdown("### 📄 PDF Report")
        st.warning("PDF generator coming soon. You'll be able to export this as a client report.")

    except Exception as e:
        st.error(f"Something went wrong: {e}")





