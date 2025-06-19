import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# --- Page Config ---
st.set_page_config(page_title="AlphaStack | Valuation Tool", layout="wide")

# --- Title ---
st.title("📊 AlphaStack: DCF & Valuation Generator")
st.markdown("Auto-valuation using just a stock ticker — or add your assumptions.")

# --- Scenario Selector ---
scenario = st.sidebar.selectbox("📈 Choose Scenario", ["Base", "Bull", "Bear"])

# --- Scenario-Based Default Assumptions ---
defaults = {
    "Base": {"revenue_growth": 10.0, "ebit_margin": 20.0, "discount_rate": 10.0},
    "Bull": {"revenue_growth": 15.0, "ebit_margin": 23.0, "discount_rate": 8.5},
    "Bear": {"revenue_growth": 6.0, "ebit_margin": 17.0, "discount_rate": 11.5}
}
d = defaults[scenario]

# --- Ticker Input ---
ticker = st.text_input("Enter Stock Ticker (e.g., INFY.NS)", value="TCS.NS")

# --- Input Section ---
st.header("🔧 Custom Assumptions (You can override scenario defaults)")
col1, col2, col3 = st.columns(3)
with col1:
    revenue_growth = st.number_input("Revenue Growth Rate (% per year)", value=d["revenue_growth"])
    tax_rate = st.number_input("Tax Rate (% of EBIT)", value=25.0)
with col2:
    ebit_margin = st.number_input("EBIT Margin (%)", value=d["ebit_margin"])
    discount_rate = st.number_input("WACC / Discount Rate (%)", value=d["discount_rate"])
with col3:
    terminal_growth = st.number_input("Terminal Growth Rate (%)", value=3.0)
    forecast_years = st.slider("Forecast Period (Years)", 3, 10, 5)

# --- Upload Optional Excel for CapEx / Dep / WC ---
st.subheader("📂 Upload Optional File for CapEx/Depreciation/WC")
uploaded_file = st.file_uploader("Upload CSV or Excel (optional)", type=["csv", "xlsx"])

# --- Show Instructions & Sample ---
with st.expander("📘 View Upload Instructions & Sample"):
    st.markdown("""
    Upload only these 3 fields (we auto-fetch the rest):

    | Year | Capital Expenditure | Depreciation | Change in Working Capital |
    |------|---------------------|--------------|----------------------------|
    | 2022 | 20                  | 10           | -5                         |
    """)
    sample_df = pd.DataFrame({
        "Year": [2022, 2023],
        "Capital Expenditure": [20, 25],
        "Depreciation": [10, 12],
        "Change in Working Capital": [-5, -4],
    })
    st.dataframe(sample_df)
    st.download_button("📥 Download Sample Template", data=sample_df.to_csv(index=False), file_name="sample_template.csv")

# --- Process Button ---
if st.button("🚀 Generate Valuation"):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        st.subheader(f"🏢 Company Profile: {info.get('shortName', 'N/A')}")
        st.write(f"Sector: {info.get('sector', 'N/A')} | Industry: {info.get('industry', 'N/A')}")
        st.write(f"Market Cap: ₹{info.get('marketCap', 0):,}")
        st.write(f"PE Ratio: {info.get('trailingPE', 'N/A')}, Beta: {info.get('beta', 'N/A')}, Dividend Yield: {info.get('dividendYield', 0) * 100:.2f}%")

        # Financials from Yahoo
        revenue = info.get("totalRevenue", 1000)
        net_income = info.get("netIncome", 200)
        cash = info.get("totalCash", 200)
        debt = info.get("totalDebt", 100)
        shares = info.get("sharesOutstanding", 50)
        ebit = revenue * (ebit_margin / 100)

        # Load uploaded CapEx / Depreciation / WC
        if uploaded_file:
            if uploaded_file.name.endswith("csv"):
                fin_df = pd.read_csv(uploaded_file)
            else:
                fin_df = pd.read_excel(uploaded_file)

            capex = fin_df.iloc[-1]["Capital Expenditure"]
            dep = fin_df.iloc[-1]["Depreciation"]
            wc = fin_df.iloc[-1]["Change in Working Capital"]
        else:
            capex = 100
            dep = 50
            wc = -20

        # --- DCF Calculation ---
        tax = ebit * (tax_rate / 100)
        nopat = ebit - tax
        fcf = nopat + dep - capex - wc

        cash_flows = []
        for year in range(1, forecast_years + 1):
            fcf_proj = fcf * ((1 + revenue_growth / 100) ** year)
            fcf_disc = fcf_proj / ((1 + discount_rate / 100) ** year)
            cash_flows.append((year, round(fcf_proj, 2), round(fcf_disc, 2)))

        df_cf = pd.DataFrame(cash_flows, columns=["Year", "Projected FCF", "Discounted FCF"])
        st.markdown("### 🔢 Forecasted Free Cash Flows")
        st.dataframe(df_cf)

        # Terminal value
        last_fcf = cash_flows[-1][1]
        terminal_val = (last_fcf * (1 + terminal_growth / 100)) / ((discount_rate / 100) - (terminal_growth / 100))
        disc_terminal = terminal_val / ((1 + discount_rate / 100) ** forecast_years)

        # Final valuation
        total_ev = sum(df_cf["Discounted FCF"]) + disc_terminal
        equity_val = total_ev + cash - debt
        intrinsic_val = equity_val / shares

        st.markdown("### 💰 Valuation Summary")
        st.success(f"Enterprise Value: ₹{round(total_ev, 2):,}")
        st.success(f"Equity Value: ₹{round(equity_val, 2):,}")
        st.success(f"Intrinsic Value per Share: ₹{round(intrinsic_val, 2):,.2f}")

        # --- Price Chart ---
        st.markdown("### 📉 1Y Stock Price Chart")
        hist = stock.history(period="1y")
        fig, ax = plt.subplots()
        hist["Close"].plot(ax=ax, title=f"{ticker} Price Trend")
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Something went wrong: {e}")

