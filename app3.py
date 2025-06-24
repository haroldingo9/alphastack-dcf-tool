import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go

# --- Page Config ---
st.set_page_config(page_title="AlphaStack: Valuation + Technical Insights", layout="wide")
st.title("📊 AlphaStack: Valuation + Technical Insights")
st.markdown("Get DCF valuation, peer comparison, technical patterns, and stress test simulation — all in one place.")

# --- Sidebar ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.selectbox("Stress Test Event", ["None", "COVID-19 (2020)", "2008 Financial Crisis", "Scam 1992", "Dotcom Bubble"])

# --- Ticker Input ---
ticker = st.text_input("Ticker (e.g., TCS.NS)", value="TCS.NS")

# --- Assumptions ---
st.subheader("🔧 DCF Assumptions")
col1, col2, col3 = st.columns(3)
with col1:
    revenue_growth = st.slider("Revenue Growth %", 0.0, 30.0, 10.0)
    terminal_growth = st.slider("Terminal Growth %", 0.0, 10.0, 3.0)
with col2:
    ebit_margin = st.slider("EBIT Margin %", 0.0, 50.0, 20.0)
    tax_rate = st.slider("Tax Rate %", 0.0, 50.0, 25.0)
with col3:
    discount_rate = st.slider("WACC %", 0.0, 30.0, 10.0)
    forecast_years = st.slider("Forecast Years", 1, 10, 5)
# ✅ Add Explanation Table Here
with st.expander("📘 What Do These Inputs Mean?"):
    explain_df = pd.DataFrame({
        "Parameter": [
            "Revenue Growth %",
            "Terminal Growth %",
            "EBIT Margin %",
            "Tax Rate %",
            "WACC %",
            "Forecast Years"
        ],
        "Meaning": [
            "Expected annual revenue growth during forecast period.",
            "Growth rate after the forecast period (used to calculate terminal value).",
            "Percentage of revenue that remains as EBIT (profitability).",
            "Percentage of EBIT paid as tax to calculate NOPAT.",
            "Discount rate (cost of capital) used to discount future cash flows.",
            "Number of years into the future for which cash flows are projected."
        ],
        "Impact on Valuation": [
            "Higher growth increases future cash flows and valuation.",
            "Slight changes greatly affect terminal value and valuation.",
            "Higher margins mean more profit and higher cash flows.",
            "Higher taxes reduce free cash flows, lowering valuation.",
            "Higher WACC decreases present value of future cash flows.",
            "Longer forecasts show more growth but add more uncertainty."
        ]
    })

    st.dataframe(explain_df, use_container_width=True)


# --- File Upload ---
st.subheader("📂 Optional Financials Upload")
uploaded_file = st.file_uploader("CSV/XLSX: Year,Revenue,EBIT,CapEx,Dep,ΔWC,Cash,Debt,Shares", type=["csv", "xlsx"])

# --- Sample Template ---
with st.expander("📘 Sample Upload Template"):
    sample_df = pd.DataFrame({
        "Year": [2020, 2021, 2022],
        "Revenue": [1000, 1200, 1400],
        "EBIT": [200, 240, 280],
        "CapEx": [50, 60, 70],
        "Dep": [30, 35, 40],
        "ΔWC": [-10, -12, -14],
        "Cash": [100, 120, 150],
        "Debt": [50, 60, 70],
        "Shares": [10, 10, 10]
    })
    st.dataframe(sample_df)
    csv = sample_df.to_csv(index=False).encode()
    st.download_button("📥 Download Sample Template", csv, "sample_template.csv")

# --- Main Action ---
if st.button("🚀 Generate Valuation"):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        name = info.get("shortName", "N/A")
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        market_cap = info.get("marketCap", 0)
        pe_ratio = info.get("trailingPE", "N/A")
        div_yield = info.get("dividendYield", 0.0) * 100

        st.markdown(f"### 🏢 {name} | {industry}")
        st.write(f"Market Cap: ₹{market_cap / 1e12:.2f}T | PE: {pe_ratio} | Div Yield: {div_yield:.2f}%")

        # --- Load Data ---
        if uploaded_file:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
            latest = df.iloc[-1]
            revenue = latest["Revenue"]
            ebit = latest["EBIT"]
            capex = latest["CapEx"]
            dep = latest["Dep"]
            wc = latest["ΔWC"]
            cash = latest["Cash"]
            debt = latest["Debt"]
            shares = latest["Shares"]
            growth_rate = ((df["Revenue"].iloc[-1] - df["Revenue"].iloc[0]) / df["Revenue"].iloc[0]) * 100 / (len(df)-1)
            revenue_growth = round(growth_rate, 2)
        else:
            revenue = info.get("totalRevenue", 1000)
            ebit = revenue * (ebit_margin / 100)
            capex, dep, wc = 100, 50, -20
            cash = info.get("totalCash", 100)
            debt = info.get("totalDebt", 50)
            shares = info.get("sharesOutstanding", 50)

        tax = ebit * (tax_rate / 100)
        nopat = ebit - tax
        fcf = nopat + dep - capex - wc

        # --- DCF ---
        cash_flows = []
        for year in range(1, forecast_years + 1):
            proj_fcf = fcf * ((1 + revenue_growth / 100) ** year)
            disc_fcf = proj_fcf / ((1 + discount_rate / 100) ** year)
            cash_flows.append((year, round(proj_fcf, 2), round(disc_fcf, 2)))

        df_cf = pd.DataFrame(cash_flows, columns=["Year", "Projected FCF", "Discounted FCF"])
        st.subheader("🔢 Forecasted Cash Flows")
        st.dataframe(df_cf)

        terminal_val = (cash_flows[-1][1] * (1 + terminal_growth / 100)) / (discount_rate / 100 - terminal_growth / 100)
        disc_terminal = terminal_val / ((1 + discount_rate / 100) ** forecast_years)
        ev = sum(df_cf["Discounted FCF"]) + disc_terminal
        equity_val = ev + cash - debt
        intrinsic_val = equity_val / shares

        st.subheader("💰 Valuation Summary")
        st.metric("Enterprise Value", f"₹{ev / 1e12:.2f}T")
        st.metric("Equity Value", f"₹{equity_val / 1e12:.2f}T")
        st.metric("Intrinsic Value/share", f"₹{intrinsic_val:,.2f}")

        price = stock.history(period="1d")["Close"].iloc[-1]
        diff = price - intrinsic_val
        pct = (diff / price) * 100
        if pct < 0:
            st.info(f"🧠 Insight: Stock appears **undervalued** by {abs(pct):.1f}% (Mkt ₹{price:.2f} vs IV ₹{intrinsic_val:.2f})")
        else:
            st.warning(f"🧠 Insight: Stock appears **overvalued** by {abs(pct):.1f}% (Mkt ₹{price:.2f} vs IV ₹{intrinsic_val:.2f})")

        if stress_event != "None":
            st.subheader("🧨 Stress Test Results")
            crisis_periods = {
                "COVID-19 (2020)": ("2020-02-01", "2020-04-01"),
                "2008 Financial Crisis": ("2008-09-01", "2009-03-01"),
                "Scam 1992": ("1992-03-01", "1992-07-01"),
                "Dotcom Bubble": ("2000-03-01", "2002-03-01"),
            }
            start, end = crisis_periods[stress_event]
            data = yf.download(ticker, start=start, end=end)
            if not data.empty:
                drop_pct = float(((data["Close"].iloc[-1] - data["Close"].iloc[0]) / data["Close"].iloc[0]) * 100)
                fall_val = float(price * (1 + drop_pct / 100))
                st.error(
                    f"If {stress_event} repeats, estimated price fall: {drop_pct:.2f}%, new price: ₹{fall_val:.2f}")

        # --- Chart ---
        st.subheader("📈 Price Chart + Technical Pattern (30D)")
        hist = stock.history(period="1mo")
        fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'],
                                             low=hist['Low'], close=hist['Close'])])
        st.plotly_chart(fig, use_container_width=True)

        # --- Technical Summary ---
        st.subheader("🧠 Technical Pattern: Summary")
        def detect_doji(df):
            return abs(df['Close'] - df['Open']) < (df['High'] - df['Low']) * 0.1

        def detect_hammer(df):
            body = abs(df['Close'] - df['Open'])
            lower = df['Open'] - df['Low']
            upper = df['High'] - df['Close']
            return (lower > 2 * body) & (upper < body)

        hist = hist.dropna()
        patterns = {
            "Doji": detect_doji(hist),
            "Hammer": detect_hammer(hist),
        }

        for pattern, condition in patterns.items():
            count = int(condition.sum())
            st.write(f"🔹 {pattern} appeared **{count}** times")

        st.caption("📘 All results are for educational purposes only. No investment advice.")

    except Exception as e:
        st.error(f"❌ Something went wrong: {e}")







