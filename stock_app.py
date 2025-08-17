# stock_app.py
import io
import tempfile
import os
from datetime import datetime, timedelta
from fpdf import FPDF

import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# -------------------------
# Page config
# -------------------------
st.set_page_config(layout="wide", page_title="Stock Data Viewer (Refresh & Export)")

# -------------------------
# Helper: cached data fetch
# -------------------------
@st.cache_data(show_spinner=False)
def get_stock_data(ticker: str, period: str = "5y"):
    """Download stock data via yfinance (cached)."""
    df = yf.download(ticker, period=period, progress=False)
    # If yfinance returns MultiIndex columns, keep only first level
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df

# -------------------------
# Header & quick instructions
# -------------------------
st.title("📈 Stock Data Viewer")
st.markdown("Interactive stock charting with Bollinger Bands & MACD — refresh data manually and export reports.")

# -------------------------
# Sidebar controls
# -------------------------
with st.sidebar:
    st.header("Controls")
    ticker = st.text_input("Ticker (example: INFY.BO, AAPL)", value="INFY.BO")
    period = st.selectbox("Data period", options=["1y", "2y", "5y", "10y"], index=2)
    st.markdown("---")
    st.markdown("**Refresh / Real-time**")
    if st.button("🔄 Refresh Data (fetch latest)"):
        # Clear cached data and rerun so fresh data is fetched
        try:
            get_stock_data.clear()
        except Exception:
            # older versions may not have clear method, try alternative:
            try:
                del st.session_state["get_stock_data"]  # not typical; safe ignore
            except Exception:
                pass
        if st.button("🔄 Refresh Data"):
           st.rerun()

    st.markdown("---")
    st.header("Export")
    pdf_request = st.button("📄 Create PDF Report")
    excel_request = st.button("📥 Prepare Excel export")
    st.markdown("---")
    st.caption("Use date selectors on main page to filter the data before exporting.")

# -------------------------
# Fetch data (cached)
# -------------------------
with st.spinner("Fetching data..."):
    raw_data = get_stock_data(ticker, period=period)

if raw_data is None or raw_data.empty:
    st.warning("No data found for this ticker & period. Check the symbol (e.g., INFY.BO) and try again.")
    st.stop()

# -------------------------
# Main UI: date range & data display
# -------------------------
st.subheader("Select Date Range & View Data")

# default date range
min_date = raw_data.index.min().date()
max_date = raw_data.index.max().date()
# show side-by-side date pickers
col_date1, col_date2, col_date3 = st.columns([1, 1, 1])
with col_date1:
    start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
with col_date2:
    end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
with col_date3:
    show_raw = st.checkbox("Show raw data table", value=False)

if start_date > end_date:
    st.error("Start Date must be before or equal to End Date.")
    st.stop()

# filter dataframe by date range (use index.date comparison to be robust)
data = raw_data.loc[(raw_data.index.date >= start_date) & (raw_data.index.date <= end_date)].copy()

# compute indicators on filtered data
def bollinger_bands(df, window=20, no_of_std=2):
    ma = df["Close"].rolling(window=window).mean()
    std = df["Close"].rolling(window=window).std()
    upper = ma + std * no_of_std
    lower = ma - std * no_of_std
    return ma, upper, lower

def macd(df, short=12, long=26, signal=9):
    exp1 = df["Close"].ewm(span=short, adjust=False).mean()
    exp2 = df["Close"].ewm(span=long, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

# Add indicator columns (safe if data is small)
if not data.empty:
    data["BB_MA"], data["BB_upper"], data["BB_lower"] = bollinger_bands(data)
    data["MACD"], data["Signal"], data["Histogram"] = macd(data)

# Show raw data table if requested
if show_raw:
    st.dataframe(data, use_container_width=True, height=300)

# -------------------------
# Chart controls (main page)
# -------------------------
st.markdown("---")
controls_col, chart_col = st.columns([1, 2])

with controls_col:
    st.header("Chart controls")
    view_type = st.radio("View Type", ["Single Metric", "Multi Metric"], index=0)
    show_bollinger = st.checkbox("Show Bollinger Bands (Close only)", value=True)
    show_macd = st.checkbox("Show MACD (separate)", value=True)
    if view_type == "Single Metric":
        metric = st.selectbox("Metric", ["Close", "Open", "High", "Low", "Volume"], index=0)
    else:
        metrics = st.multiselect("Metrics (multi)", ["Close", "Open", "High", "Low", "Volume"], default=["Close", "Open", "High"])

with chart_col:
    st.header("Charts")
    if data.empty:
        st.warning("No data in selected date range.")
    else:
        fig_main = None
        # Single metric view
        if view_type == "Single Metric":
            if metric == "Close":
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=data.index, y=data["Close"], name="Close", mode="lines", line=dict(color="cyan", width=2)))
                # MA50 & MA200 for context
                data["MA50"] = data["Close"].rolling(50).mean()
                data["MA200"] = data["Close"].rolling(200).mean()
                fig.add_trace(go.Scatter(x=data.index, y=data["MA50"], name="MA50", mode="lines", line=dict(color="orange", width=1.5)))
                fig.add_trace(go.Scatter(x=data.index, y=data["MA200"], name="MA200", mode="lines", line=dict(color="green", width=1.5)))
                if show_bollinger:
                    fig.add_trace(go.Scatter(x=data.index, y=data["BB_upper"], name="BB Upper", mode="lines", line=dict(color="magenta", dash="dash", width=1)))
                    fig.add_trace(go.Scatter(x=data.index, y=data["BB_lower"], name="BB Lower", mode="lines", line=dict(color="magenta", dash="dash", width=1)))
                    fig.add_trace(go.Scatter(x=data.index, y=data["BB_MA"], name="BB MA (20)", mode="lines", line=dict(color="orange", width=1)))
                fig.update_layout(title=f"{ticker} — Close", template="plotly_dark", height=520, legend=dict(orientation="h"))
                st.plotly_chart(fig, use_container_width=True)
                fig_main = fig
                # Show Bollinger explanation only when toggled
                if show_bollinger:
                    st.markdown(
                        "- **Bollinger Bands:** middle=20-day MA, upper/lower = ±2 std dev.\n"
                        "- Bands widen when volatility is high and contract when low.\n"
                        "- Price near upper band may indicate overbought; near lower band may indicate oversold."
                    )
            else:
                fig = px.line(data, x=data.index, y=metric, title=f"{ticker} — {metric}", template="plotly_dark", height=520)
                st.plotly_chart(fig, use_container_width=True)
                fig_main = fig

        # Multi metric view
        else:
            df_plot = data.copy()
            legend_names = {}
            if "Volume" in metrics:
                # scale volume for visibility
                max_price = df_plot[["Close", "Open", "High", "Low"]].max().max()
                df_plot["Volume_scaled"] = (df_plot["Volume"] / df_plot["Volume"].max()) * max_price
                legend_names["Volume_scaled"] = "Volume"
                metrics = [m if m != "Volume" else "Volume_scaled" for m in metrics]
            fig = px.line(df_plot, x=df_plot.index, y=metrics, title=f"{ticker} — Multiple metrics", template="plotly_dark", height=520)
            fig.for_each_trace(lambda t: t.update(name=legend_names.get(t.name, t.name)))
            st.plotly_chart(fig, use_container_width=True)
            fig_main = fig

        # MACD chart (separate) if requested
        if show_macd and not data.empty:
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Scatter(x=data.index, y=data["MACD"], name="MACD", line=dict(color="cyan")))
            fig_macd.add_trace(go.Scatter(x=data.index, y=data["Signal"], name="Signal", line=dict(color="orange")))
            fig_macd.add_trace(go.Bar(x=data.index, y=data["Histogram"], name="Histogram", marker_color="gray"))
            fig_macd.update_layout(title=f"{ticker} — MACD", template="plotly_dark", height=300, legend=dict(orientation="h"))
            st.plotly_chart(fig_macd, use_container_width=True)
            # MACD explanation shown only when chart visible
            st.markdown(
                "- **MACD:** MACD = 12-EMA − 26-EMA; Signal = 9-EMA of MACD.\n"
                "- Histogram = MACD − Signal. Crossovers may indicate buy/sell signals."
            )

# -------------------------
# Export (CSV, Excel, PDF)
# -------------------------
st.markdown("---")
st.header("Export / Download")

# CSV download
csv_bytes = data.to_csv().encode("utf-8")
st.download_button("Download CSV (filtered)", data=csv_bytes, file_name=f"{ticker}_filtered.csv", mime="text/csv")

# Excel download (in-memory)
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="data", index=True)
    return towrite.getvalue()

excel_bytes = df_to_excel_bytes(data)
st.download_button("Download Excel (filtered)", data=excel_bytes, file_name=f"{ticker}_filtered.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# PDF report creation (chart image + small summary)
def create_pdf(fig: go.Figure, df: pd.DataFrame, ticker_sym: str) -> bytes:
    # Try to export the Plotly figure to PNG using kaleido
    img_bytes = None
    try:
        img_bytes = fig.to_image(format="png", scale=2)
    except Exception as e:
        # fallback: None (we'll note in pdf)
        img_bytes = None

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, f"Stock Report — {ticker_sym}", ln=True, align="C")
    pdf.ln(4)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(6)

    # Insert chart image if available
    if img_bytes is not None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(img_bytes)
        tmp.flush()
        tmp.close()
        # Insert full-width image (A4 width ~ 190mm printable area)
        try:
            pdf.image(tmp.name, x=10, y=None, w=190)
        except Exception:
            # if image insertion fails, just skip
            pass
        finally:
            os.unlink(tmp.name)
        pdf.ln(6)
    else:
        pdf.set_font("Arial", "I", 10)
        pdf.multi_cell(0, 5, "Chart image not available (kaleido may be missing). The data summary follows.")
        pdf.ln(6)

    # Add small data summary table (last 5 rows)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Data summary (last 5 rows):", ln=True)
    pdf.set_font("Arial", size=9)

    last_rows = df.tail(5).reset_index()
    headers = list(last_rows.columns)
    col_w = [28] * len(headers)
    # Header
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 6, str(h), border=1)
    pdf.ln()
    # Rows
    for _, row in last_rows.iterrows():
        for i, val in enumerate(row):
            txt = str(val)
            if len(txt) > 18:
                txt = txt[:15] + "..."
            pdf.cell(col_w[i], 6, txt, border=1)
        pdf.ln()

    return pdf.output(dest="S").encode("latin-1")

# Trigger export actions when buttons in the sidebar were clicked
exported = False
if excel_request:
    st.success("Excel export prepared — click the button below to download.")
    st.download_button("Download prepared Excel (.xlsx)", data=excel_bytes, file_name=f"{ticker}_filtered.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    exported = True

if pdf_request:
    if 'fig_main' in locals() and fig_main is not None:
        try:
            pdf_bytes = create_pdf(fig_main, data, ticker)
            st.success("PDF report prepared — click the button below to download.")
            st.download_button("Download PDF report", data=pdf_bytes, file_name=f"{ticker}_report.pdf", mime="application/pdf")
            exported = True
        except Exception as e:
            st.error(f"Failed to create PDF: {e}")
    else:
        st.error("No main chart available to include in PDF. Generate a chart first.")

if not exported:
    st.info("Use the Download buttons above to get CSV/Excel or click 'Create PDF Report' in the sidebar to prepare a PDF (includes current main chart).")

# -------------------------
# Footer / small note
# -------------------------
st.markdown("---")
st.caption("Tip: use the Refresh Data button in the sidebar to fetch the latest quotes when needed.")
