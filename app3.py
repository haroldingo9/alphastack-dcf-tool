import streamlit as st
import pandas as pd

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

# --- File Upload ---
uploaded_file = st.file_uploader("Or upload your own financials (CSV or Excel)", type=["csv", "xlsx"])

# --- Instructions + Sample Table ---
with st.expander("📘 View Upload Instructions & Sample"):
    st.markdown("""
    Your file should contain historical financials in the following format:

    | Year | Revenue | EBIT | Net Income | Capital Expenditure | Depreciation | Change in Working Capital | Cash | Debt | Shares Outstanding |
    |------|---------|------|------------|----------------------|--------------|----------------------------|------|------|---------------------|
    | 2021 | 500     | 100  | 80         | 20                   | 10           | -5                         | 200  | 100  | 50                  |
    | 2022 | 550     | 110  | 85         | 25                   | 12           | -4                         | 220  | 90   | 50                  |

    - **Units**: ₹ Crores (or your preferred currency)  
    - Include at least 2 years of historical data  
    - Column headers must match exactly
    """)

    sample_data = pd.DataFrame({
        "Year": [2021, 2022],
        "Revenue": [500, 550],
        "EBIT": [100, 110],
        "Net Income": [80, 85],
        "Capital Expenditure": [20, 25],
        "Depreciation": [10, 12],
        "Change in Working Capital": [-5, -4],
        "Cash": [200, 220],
        "Debt": [100, 90],
        "Shares Outstanding": [50, 50]
    })
    st.dataframe(sample_data)

    sample_csv = sample_data.to_csv(index=False)
    st.download_button("📥 Download Sample Template", data=sample_csv, file_name="valuation_template.csv", mime="text/csv")

# --- Submit Button ---
generate = st.button("🚀 Generate Valuation")

# --- Logic ---
if generate:
    st.subheader("📈 Valuation Results")

    if uploaded_file:
        if uploaded_file.name.endswith("csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        st.markdown("✅ Uploaded Financials:")
        st.dataframe(df)

        last_row = df.iloc[-1]
        revenue = last_row["Revenue"]
        ebit = last_row["EBIT"]
        capex = last_row["Capital Expenditure"]
        dep = last_row["Depreciation"]
        wc_change = last_row["Change in Working Capital"]
        cash = last_row["Cash"]
        debt = last_row["Debt"]
        shares_outstanding = last_row["Shares Outstanding"]
    else:
        st.warning("No file uploaded. Using default sample values.")
        revenue = 1000
        ebit = revenue * (ebit_margin / 100)
        capex = 100
        dep = 50
        wc_change = -20
        cash = 200
        debt = 100
        shares_outstanding = 50

    # --- DCF Calculation ---
    ebit = revenue * (ebit_margin / 100)
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

    last_fcf = cash_flows[-1][1]
    terminal_value = (last_fcf * (1 + terminal_growth / 100)) / ((discount_rate / 100) - (terminal_growth / 100))
    discounted_terminal = terminal_value / ((1 + discount_rate / 100) ** forecast_years)

    st.markdown("### 🧮 Terminal Value")
    st.write(f"Terminal Value: ₹{round(terminal_value, 2)}")
    st.write(f"Discounted Terminal Value: ₹{round(discounted_terminal, 2)}")

    total_enterprise_value = discounted_terminal + sum([val[2] for val in cash_flows])
    equity_value = total_enterprise_value + cash - debt
    intrinsic_value_per_share = equity_value / shares_outstanding

    st.markdown("### 💰 Valuation Summary")
    st.success(f"**Enterprise Value:** ₹{round(total_enterprise_value, 2)}")
    st.success(f"**Equity Value:** ₹{round(equity_value, 2)}")
    st.success(f"**Intrinsic Value per Share:** ₹{round(intrinsic_value_per_share, 2)}")

    st.caption("All values are estimates based on assumptions or uploaded.")