import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# --- Page Configuration ---
st.set_page_config(page_title="AlphaStack | DCF Tool", layout="wide")

# --- Title ---
st.title("📊 AlphaStack: Multi‑Model Valuation Generator")
st.markdown("Choose your valuation model or upload your own numbers.")

# --- Sidebar Settings ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.selectbox("Stress Test Event", [
    "None", "COVID‑19 (2020)", "2008 Financial Crisis", "Great Depression", "Scam 1992"
])
model = st.sidebar.selectbox("Valuation Model", ["DCF", "Relative (P/E)", "Dividend Discount (DDM)"])

# --- Main Inputs ---
ticker = st.text_input("Enter Stock Ticker (e.g., TCS.NS)", "TCS.NS")

# --- Sliders for Assumptions ---
st.header("🔧 Assumptions (Sliders)")
col1, col2 = st.columns(2)
with col1:
    revenue_growth  = st.slider("Revenue Growth (% p.a.)",       0.0, 30.0, 10.0, 0.1)
    ebit_margin     = st.slider("EBIT Margin (%)",              0.0, 50.0, 20.0, 0.1)
    terminal_growth = st.slider("Terminal Growth Rate (%)",     0.0, 10.0,  3.0, 0.1)
with col2:
    tax_rate        = st.slider("Tax Rate (% of EBIT)",         0.0, 50.0, 25.0, 0.1)
    discount_rate   = st.slider("Discount Rate (WACC %)",       0.0, 30.0, 10.0, 0.1)
    forecast_years  = st.slider("Forecast Period (Years)",        1, 10,     5)

# --- Optional CSV/Excel Upload ---
st.subheader("📂 Upload Your Financials (Optional override)")
uploaded = st.file_uploader(
    "CSV/Excel with columns: Year, Revenue, EBIT, Net Income, CapEx, Depreciation, ΔWC, Cash, Debt, Shares",
    type=["csv","xlsx"]
)
if uploaded:
    df_fin = pd.read_csv(uploaded) if uploaded.name.endswith("csv") else pd.read_excel(uploaded)
    latest = df_fin.iloc[-1]
    rev_override  = latest.get("Revenue")
    ebit_override = latest.get("EBIT")
    capex         = latest.get("CapEx")
    dep           = latest.get("Depreciation")
    wc            = latest.get("ΔWC")
    cash          = latest.get("Cash")
    debt          = latest.get("Debt")
    shares        = latest.get("Shares")
else:
    rev_override = ebit_override = capex = dep = wc = cash = debt = shares = None

# --- Run Valuation ---
if st.button("🚀 Generate Valuation"):
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info
        hist  = stock.history(period="1y")

        # Company snapshot
        st.subheader(f"🏢 {info.get('shortName', ticker)}")
        st.write(f"Sector: {info.get('sector','N/A')} | Industry: {info.get('industry','N/A')}")
        st.write(f"Market Cap: ₹{info.get('marketCap',0):,} | PE: {info.get('trailingPE','N/A')} | Div Yield: {info.get('dividendYield',0)*100:.2f}%")

        # Base financials (override if uploaded)
        revenue = rev_override  or info.get("totalRevenue", 1e3)
        ebit    = ebit_override or revenue * (ebit_margin/100)
        cash    = cash         or info.get("totalCash", 0)
        debt    = debt         or info.get("totalDebt", 0)
        shares  = shares       or info.get("sharesOutstanding", 1)

        capex   = capex or 0
        dep     = dep   or 0
        wc      = wc    or 0

        # 1) DCF Model
        def run_dcf():
            tax   = ebit * (tax_rate/100)
            nopat = ebit - tax
            base_fcf = nopat + dep - capex - wc

            rows=[]
            for yr in range(1, forecast_years+1):
                proj = base_fcf * ((1+revenue_growth/100)**yr)
                disc = proj / ((1+discount_rate/100)**yr)
                rows.append((yr, round(proj,2), round(disc,2)))
            df = pd.DataFrame(rows, columns=["Year","Proj FCF","Disc FCF"])
            st.markdown("### 🔢 DCF Cash Flows")
            st.dataframe(df)

            last = rows[-1][1]
            tv   = (last*(1+terminal_growth/100)) / ((discount_rate/100)-(terminal_growth/100))
            dtv  = tv/((1+discount_rate/100)**forecast_years)
            ev   = df["Disc FCF"].sum()+dtv
            eqv  = ev + cash - debt
            iv   = eqv/shares
            return ev, eqv, iv

        # 2) Relative P/E Model
        def run_pe():
            eps = info.get("trailingEps") or info.get("forwardEps") or (ebit/shares)
            pe  = info.get("trailingPE") or 0
            iv  = eps * pe
            st.markdown(f"### 🔢 Relative Valuation (P/E Model)\n- EPS: {eps:.2f}\n- P/E: {pe:.2f}")
            return None, None, iv

        # 3) Dividend Discount Model
        def run_ddm():
            div = info.get("dividendRate") or 0
            if div and (discount_rate/100 - terminal_growth/100)>0:
                iv = div / (discount_rate/100 - terminal_growth/100)
                st.markdown(f"### 🔢 Dividend Discount Model\n- Dividend/Share: {div:.2f}")
                return None, None, iv
            else:
                st.warning("No dividend data or invalid rates for DDM.")
                return None, None, None

        # Execute selected model
        if model=="DCF":
            ev, eqv, iv = run_dcf()
        elif model=="Relative (P/E)":
            ev, eqv, iv = run_pe()
        else:  # DDM
            ev, eqv, iv = run_ddm()

        # Show results
        if iv:
            if ev and eqv:
                st.success(f"Enterprise Value: ₹{ev:,.2f}")
                st.success(f"Equity Value:     ₹{eqv:,.2f}")
            st.success(f"Intrinsic Value per Share: ₹{iv:,.2f}")

            price = hist["Close"].iloc[-1]
            pct   = (iv-price)/price*100
            if pct>0:
                st.info(f"🧠 Insight: Undervalued by {pct:.1f}% (market ₹{price:.2f} vs IV ₹{iv:.2f})")
            else:
                st.warning(f"🧠 Insight: Overvalued by {abs(pct):.1f}% (market ₹{price:.2f} vs IV ₹{iv:.2f})")

        # 1Y Price Chart
        fig,ax=plt.subplots()
        hist["Close"].plot(ax=ax,title=f"{ticker} 1Y Price Trend")
        st.pyplot(fig)

        # Stress Test
        if stress_event!="None":
            events={
                "COVID‑19 (2020)":("2020-02-15","2020-03-23"),
                "2008 Financial Crisis":("2008-09-01","2008-10-15"),
                "Great Depression":("1929-09-01","1930-06-01"),
                "Scam 1992":("1992-04-01","1992-05-15")
            }
            s,e=events[stress_event]
            crash=yf.download(ticker,start=s,end=e)
            if not crash.empty:
                p0,p1=crash["Close"].iloc[0],crash["Close"].iloc[-1]
                drop=(p1-p0)/p0*100
                sim=price*(1+drop/100)
                st.markdown("### 🧨 Stress Test")
                st.warning(f"During {stress_event}, fell {drop:.1f}%")
                st.info(f"Simulated today: ₹{sim:.2f} vs ₹{price:.2f}")
            else:
                st.error("No data for that event.")

    except Exception as e:
        st.error(f"Error: {e}")






