import streamlit as st
import pandas as pd
import yfinance as yf

# --- Page Config ---
st.set_page_config(page_title="AlphaStack | Valuation Tool", layout="wide")

# --- Title ---
st.title("📊 AlphaStack: DCF & Valuation Generator")
st.markdown("Generate high-quality company valuations using your assumptions — instantly.")

# --- Input Section ---
st.header("🔧 Input Assumptions")
ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS)", value="TCS.NS")

col1, col2, col3 = st.columns(3)
with col1:
    revenue_growth = st.number_input("Revenue Growth Rate (% per year)", value=10.0)
    tax_rate = st.number_input("Tax Rate (% of EBIT)", value=25.0)

with col2:
    ebit_margin = st.number_input("EBIT Margin (%)", value=20.0)
    discount_rate = st.number_input("WACC / Discount Rate (%)", value=10.0)

with col3:
    terminal_growth = st.number_input("Terminal Growth Rate (%)", value=3.0)
    forecast_years = st.slider("Forecast Period (Years)", 3, 10, 5)

uploaded_file = st.file_uploader("Optional: Upload additional financials (CapEx, Depreciation, WC)", type=["csv", "xlsx"])

# --- Instructions ---
with st.expander("📘 Upload Format Instructions"):
    st.markdown("""
    Only upload if you want to provide **Capital Expenditure, Depreciation, and Working Capital** manually.

    | Year | Capital Expenditure | Depreciation | Change in Working Capital |
    |------|---------------------|--------------|----------------------------|
    | 2022 | 100                 | 40           | -10                        |
    | 2023 | 120                 | 42           | -5                         |
    """)

# --- Submit ---
generate = st.button("🚀 Generate Valuation")

if generate:
    st.subheader("📈 Valuation Results")
    use_uploaded = False

    # 1. Fetch from yfinance
    try:
        stock = yf.Ticker(ticker)
        fin = stock.financials
        bs = stock.balance_sheet
        shares = stock.info.get("sharesOutstanding", 0)

        # Take most recent year available
        latest_year = fin.columns[0]
        revenue = fin.loc["Total Revenue"][latest_year]
        ebit = fin.loc["Ebit"][latest_year]
        net_income = fin.loc["Net Income"][latest_year]
        cash = bs.loc["Cash"][latest_year]
        debt = bs.loc["Total Debt"][latest_year]

        st.success(f"Fetched Data for {ticker}:")
        st.write(f"Revenue: ₹{round(revenue/1e7, 2)} Cr")
        st.write(f"EBIT: ₹{round(ebit/1e7, 2)} Cr")
        st.write(f"Net Income: ₹{round(net_income/1e7, 2)} Cr")
        st.write(f"Cash: ₹{round(cash/1e7, 2)} Cr")
        st.write(f"Debt: ₹{round(debt/1e7, 2)} Cr")
        st.write(f"Shares Outstanding: {int(shares/1e6)} Million")

        revenue /= 1e7
        ebit /= 1e7
        net_income /= 1e7
        cash /= 1e7
        debt /= 1e7
        shares_outstanding = shares / 1e6

    except:
        st.error("❌ Could not fetch data. Please check the ticker or try again.")
        st.stop()

    # 2. Use uploaded CapEx, Dep, WC if available
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith("csv") else pd.read_excel(uploaded_file)
            latest_row = df.iloc[-1]
            capex = latest_row["Capital Expenditure"]
            dep = latest_row["Depreciation"]
            wc_change = latest_row["Change in Working Capital"]
            st.info("Used uploaded CapEx, Depreciation, and WC values.")
        except:
            st.warning("Upload format invalid. Using default estimates.")
            capex, dep, wc_change = 100, 50, -10
    else:
        capex, dep, wc_change = 100, 50, -10
        st.warning("No upload provided. Using default CapEx/Dep/WC values.")

    # --- DCF Calculation ---
    tax = ebit * (tax_rate / 100)
    nopat = ebit - tax
    fcf = nopat + dep - capex - wc_change

    cash_flows = []
    for year in range(1, forecast_years + 1):
        projected_fcf = fcf * ((1 + revenue_growth / 100) ** year)
        discounted_fcf = projected_fcf / ((1 + discount_rate / 100) ** year)
        cash_flows.append((year, round(projected_fcf, 2), round(discounted_fcf, 2)))

    df_cf = pd.DataFrame(cash_flows, columns=["Year", "Projected FCF", "Discounted FCF"])
    st.markdown("### 🔢 Forecasted Free Cash Flows")
    st.dataframe(df_cf)

    # Terminal value
    last_fcf = cash_flows[-1][1]
    terminal_value = (last_fcf * (1 + terminal_growth / 100)) / ((discount_rate / 100) - (terminal_growth / 100))
    discounted_terminal = terminal_value / ((1 + discount_rate / 100) ** forecast_years)

    st.markdown("### 🧮 Terminal Value")
    st.write(f"Terminal Value: ₹{round(terminal_value, 2)}")
    st.write(f"Discounted Terminal Value: ₹{round(discounted_terminal, 2)}")

    # Enterprise and Equity
    total_enterprise_value = discounted_terminal + sum([cf[2] for cf in cash_flows])
    equity_value = total_enterprise_value + cash - debt
    intrinsic_value = equity_value / shares_outstanding

    st.markdown("### 💰 Valuation Summary")
    st.success(f"Enterprise Value: ₹{round(total_enterprise_value, 2)} Cr")
    st.success(f"Equity Value: ₹{round(equity_value, 2)} Cr")
    st.success(f"Intrinsic Value per Share: ₹{round(intrinsic_value, 2)}")

    st.caption("All values are estimates based on public data and user assumptions.")
