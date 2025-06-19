import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(page_title="AlphaStack | Valuation Tool", layout="wide")
st.title("📊 AlphaStack: Multi‑Model Valuation Generator")
st.markdown("Choose your valuation model or upload your own numbers.")

# --- Sidebar Settings ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.selectbox("Stress Test Event", ["None", "COVID-19 (2020)", "2008 Financial Crisis"])
valuation_model = st.sidebar.selectbox("Valuation Model", ["DCF"])

# --- Ticker Input ---
ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS)", value="TCS.NS")

# --- Assumptions ---
st.header("🔧 Assumptions (Sliders)")
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

# --- Upload Optional Financials ---
st.subheader("📂 Upload Your Financials (Optional override)")
uploaded_file = st.file_uploader("CSV/Excel with columns: Year, Revenue, EBIT, Net Income, CapEx, Depreciation, ΔWC, Cash, Debt, Shares", type=["csv", "xlsx"])

# Sample download
with st.expander("📘 Sample Upload Template"):
    sample_data = pd.DataFrame({
        "Year": [2023],
        "Revenue": [1000],
        "EBIT": [200],
        "Net Income": [150],
        "CapEx": [80],
        "Depreciation": [40],
        "ΔWC": [-20],
        "Cash": [100],
        "Debt": [50],
        "Shares": [10]
    })
    st.dataframe(sample_data)
    st.download_button("📥 Download Sample Template", data=sample_data.to_csv(index=False), file_name="sample_template.csv")

# --- Valuation Engine ---
if st.button("🚀 Generate Valuation"):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        st.subheader(f"🏢 {info.get('shortName', 'N/A')}")
        st.write(f"Sector: {info.get('sector', 'N/A')} | Industry: {info.get('industry', 'N/A')}")
        st.write(f"Market Cap: ₹{info.get('marketCap', 0):,.0f} | PE: {info.get('trailingPE', 'N/A')} | Div Yield: {info.get('dividendYield', 0) * 100:.2f}%")

        # Use uploaded financials or defaults
        if uploaded_file:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith("csv") else pd.read_excel(uploaded_file)
            last = df.iloc[-1]
            rev = last["Revenue"]
            ebit = last["EBIT"]
            capex = last["CapEx"]
            dep = last["Depreciation"]
            wc = last["ΔWC"]
            cash = last["Cash"]
            debt = last["Debt"]
            shares = last["Shares"]
        else:
            rev = info.get("totalRevenue", 1000)
            ebit = rev * (ebit_margin / 100)
            capex = 100
            dep = 50
            wc = -20
            cash = info.get("totalCash", 100)
            debt = info.get("totalDebt", 50)
            shares = info.get("sharesOutstanding", 10)

        tax = ebit * (tax_rate / 100)
        nopat = ebit - tax
        fcf = nopat + dep - capex - wc

        cashflows = []
        for year in range(1, forecast_years + 1):
            fcf_proj = fcf * ((1 + revenue_growth / 100) ** year)
            fcf_disc = fcf_proj / ((1 + discount_rate / 100) ** year)
            cashflows.append((year, fcf_proj, fcf_disc))

        df_cf = pd.DataFrame(cashflows, columns=["Year", "Projected FCF", "Discounted FCF"])
        st.subheader("🔢 DCF Cash Flows")
        st.dataframe(df_cf)

        # Terminal Value
        terminal_fcf = cashflows[-1][1]
        terminal_val = (terminal_fcf * (1 + terminal_growth / 100)) / ((discount_rate / 100) - (terminal_growth / 100))
        disc_terminal = terminal_val / ((1 + discount_rate / 100) ** forecast_years)
        total_ev = df_cf["Discounted FCF"].sum() + disc_terminal
        equity_val = total_ev + cash - debt
        intrinsic_val = equity_val / shares

        st.success(f"Enterprise Value: ₹{total_ev:,.2f}")
        st.success(f"Equity Value: ₹{equity_val:,.2f}")
        st.success(f"Intrinsic Value per Share: ₹{intrinsic_val:,.2f}")

        # AI Insight
        current_price = stock.history(period="1d")["Close"].iloc[-1]
        diff_pct = ((intrinsic_val - current_price) / current_price) * 100
        direction = "undervalued" if diff_pct > 0 else "overvalued"
        st.markdown(f"🧠 Insight: **{direction.capitalize()}** by {abs(diff_pct):.1f}% (market ₹{current_price:.2f} vs IV ₹{intrinsic_val:.2f})")

        # Stress Test
        if stress_event != "None":
            events = {
                "COVID-19 (2020)": ("2020-02-01", "2020-04-01"),
                "2008 Financial Crisis": ("2008-09-01", "2008-11-01")
            }
            start, end = events[stress_event]
            crisis_data = yf.download(ticker, start=start, end=end)
            if not crisis_data.empty:
                pct_drop = ((crisis_data["Close"].iloc[-1] - crisis_data["Close"].iloc[0]) / crisis_data["Close"].iloc[0]) * 100
                st.markdown(f"🧨 Stress Test: During **{stress_event}**, this stock fell **{pct_drop:.2f}%**.")

        # Chart
        st.subheader("📈 Stock Chart (1Y)")
        hist = stock.history(period="1y")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Close"))
        fig.update_layout(title=f"{ticker} Price Chart", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Something went wrong: {e}")






