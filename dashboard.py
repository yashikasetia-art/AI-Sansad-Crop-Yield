"""Streamlit dashboard for the offline-first Cropwise AI application."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from api_integration.upag_client import UPAgAPIError, UPAgClient
from cropwise.analysis import analyze_variability, rank_crops
from cropwise.dataset_adapter import adapt_yield_data, load_table, select_season
from cropwise.ml import detect_yield_anomalies, evaluate_forecasts
from cropwise.service import (
    DISTRICT_SOURCE,
    HISTORICAL_SOURCE,
    STATE_SOURCE,
    ensure_local_database,
    load_district_yields,
    load_state_yields,
    load_yield_file,
    saved_annual_yields,
)


load_dotenv(Path(__file__).resolve().parent / ".env")
st.set_page_config(page_title="Cropwise AI | Yield Intelligence", page_icon="🌾", layout="wide")
st.markdown(
    """
    <style>
    :root { --ink: #153247; --green: #2a765d; --teal: #157b83; --paper: #f3f7f4; }
    .stApp { background: linear-gradient(135deg, #f3f7f4 0%, #edf4f3 55%, #f8faf7 100%); color: var(--ink); }
    [data-testid="stSidebar"] { background: #153247; }
    [data-testid="stSidebar"] * { color: #f4fbf7 !important; }
    h1, h2, h3 { color: var(--ink); }
    div[data-testid="stMetric"] { background: #ffffff; border-left: 3px solid var(--green); padding: 12px 14px; border-radius: 4px; }
    div[data-testid="stMetricValue"] { color: var(--ink); }
    div[data-testid="stAlert"] { border-radius: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_store():
    return ensure_local_database()


store, seed_status = get_store()
historical = saved_annual_yields(store)
metrics = analyze_variability(historical) if not historical.empty else pd.DataFrame()

st.sidebar.title("CALYX / CROPWISE AI")
st.sidebar.caption("Crop yield stability and volatility intelligence")
page = st.sidebar.radio(
    "Workspace",
    ["Home", "Yield Overview", "Variability", "State & Season", "AI/ML Insights", "Risk Intelligence", "Data & Reports"],
)
st.sidebar.divider()
st.sidebar.caption(f"Data: {seed_status['source']}")
st.sidebar.caption(f"Stored yield records: {store.counts()['yield_records']:,}")


def _empty_state(message: str) -> None:
    st.info(message)


def _make_pdf(frame: pd.DataFrame, title: str) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), title=title)
    selected_columns = [column for column in ("Crop", "ObservationCount", "MeanYield", "CVPercent", "DetrendedCVPercent", "TrendDirection", "StabilityClass") if column in frame]
    table_data = [[str(column) for column in selected_columns]]
    for row in frame[selected_columns].itertuples(index=False, name=None):
        table_data.append(["" if pd.isna(value) else f"{value:.2f}" if isinstance(value, (float, int)) else str(value) for value in row])
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#153247")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd8d2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf4f1")]),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    document.build([table])
    return output.getvalue()


if page == "Home":
    st.title("Crop Yield Intelligence")
    st.caption("Historical variability is descriptive evidence, not a causal explanation or a guaranteed forecast.")
    if historical.empty:
        _empty_state("No annual yield records are available in the local database.")
    else:
        eligible = metrics.loc[metrics["StabilityClass"].ne("Insufficient data")]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Annual observations", f"{len(historical):,}")
        col2.metric("Crops analyzed", f"{len(eligible):,}")
        col3.metric("Coverage", f"{historical['Year'].nunique()} crop years")
        col4.metric("Unit", historical["YieldUnit"].dropna().iloc[0] if "YieldUnit" in historical and historical["YieldUnit"].notna().any() else "Source unit")
        left, right = st.columns([1.5, 1])
        with left:
            crop_choice = st.selectbox("Yield trend", sorted(historical["Crop"].unique()), key="home_crop")
            crop_data = historical.loc[historical["Crop"].eq(crop_choice)].sort_values("Year")
            st.plotly_chart(px.line(crop_data, x="Year", y="Yield", markers=True, title=f"{crop_choice}: annual yield (source Total)", labels={"Yield": "Yield (Kg/Ha)"}), use_container_width=True)
        with right:
            st.subheader("Current evidence")
            st.write(f"**Data source:** {seed_status['source']}")
            st.write(f"**Reporting status:** {historical['ReportingStatus'].dropna().iloc[0] if historical['ReportingStatus'].notna().any() else 'Not provided'}")
            st.write("Annual comparisons use source `Total` records. Seasonal records are not added to annual totals.")
            st.write("Use the state panel for recent geography; its short coverage is not suitable for long-term state volatility claims.")

elif page == "Yield Overview":
    st.title("Crop Yield Overview")
    if historical.empty:
        _empty_state("No annual yield records are available.")
    else:
        crops = sorted(historical["Crop"].unique())
        selected = st.selectbox("Crop", crops)
        series = historical.loc[historical["Crop"].eq(selected)].sort_values("Year")
        summary = metrics.loc[metrics["Crop"].eq(selected)]
        if not summary.empty:
            row = summary.iloc[0]
            a, b, c, d = st.columns(4)
            a.metric("Mean yield", f"{row['MeanYield']:,.1f} Kg/Ha")
            b.metric("Median yield", f"{row['MedianYield']:,.1f} Kg/Ha")
            c.metric("Observed range", f"{row['MinimumYield']:,.0f}–{row['MaximumYield']:,.0f}")
            d.metric("Trend", str(row["TrendDirection"]))
        st.plotly_chart(px.line(series, x="Year", y="Yield", markers=True, title=f"{selected} annual yield", labels={"Yield": "Yield (Kg/Ha)"}), use_container_width=True)
        st.dataframe(series[["Year", "Yield", "YieldUnit", "Source", "ReportingStatus"]], use_container_width=True, hide_index=True)

elif page == "Variability":
    st.title("Yield Variability")
    if metrics.empty:
        _empty_state("There are not enough source observations to calculate variability.")
    else:
        st.caption("Detrended CV = sample SD of linear-trend residuals / mean observed yield × 100. Classes use empirical quantiles in the current cohort, not official thresholds.")
        a, b = st.columns(2)
        with a:
            st.subheader("Lowest detrended variability")
            st.dataframe(rank_crops(metrics)["stable"], use_container_width=True, hide_index=True)
        with b:
            st.subheader("Highest detrended variability")
            st.dataframe(rank_crops(metrics)["variable"], use_container_width=True, hide_index=True)
        chart = metrics.loc[metrics["StabilityClass"].ne("Insufficient data")].sort_values("DetrendedCVPercent", ascending=True)
        st.plotly_chart(px.bar(chart, x="Crop", y="DetrendedCVPercent", color="StabilityClass", title="Detrended variability by crop", labels={"DetrendedCVPercent": "Detrended CV (%)"}), use_container_width=True)
        st.dataframe(metrics, use_container_width=True, hide_index=True)

elif page == "State & Season":
    st.title("State and Seasonal Analysis")
    state_tab, season_tab, district_tab = st.tabs(["Recent state panel", "National seasons", "District snapshot"])
    with state_tab:
        if not STATE_SOURCE.exists():
            _empty_state("The recent state-wise CSV is not present in the workspace.")
        else:
            state_data = load_state_yields()
            states = sorted(state_data["State"].dropna().unique())
            state = st.selectbox("State", states, key="state_panel")
            state_crops = sorted(state_data.loc[state_data["State"].eq(state), "Crop"].dropna().unique())
            crop = st.selectbox("Crop", state_crops, key="state_crop")
            series = state_data.loc[state_data["State"].eq(state) & state_data["Crop"].eq(crop)].sort_values("Year")
            st.caption("Coverage is 2021–22 to 2025–26 where reported. Missing observations remain missing; 2025–26 reporting is not independently verified.")
            st.plotly_chart(px.line(series, x="Year", y="Yield", markers=True, title=f"{crop} in {state}", labels={"Yield": "Yield (Kg/Ha)"}), use_container_width=True)
            st.dataframe(series, use_container_width=True, hide_index=True)
    with season_tab:
        seasonal = load_yield_file(HISTORICAL_SOURCE, annual_total=False, yield_unit="Kg/Ha")
        if "Season" not in seasonal:
            _empty_state("The historical source does not contain a season field.")
        else:
            seasonal_crops = sorted(seasonal["Crop"].unique())
            crop = st.selectbox("Crop", seasonal_crops, key="season_crop")
            subset = seasonal.loc[seasonal["Crop"].eq(crop) & seasonal["Season"].ne("Total")]
            st.plotly_chart(px.line(subset, x="Year", y="Yield", color="Season", markers=True, title=f"{crop}: seasonal yield", labels={"Yield": "Yield (Kg/Ha)"}), use_container_width=True)
            st.caption("Season-specific series are compared as reported; Total rows are excluded from this chart.")
    with district_tab:
        if not DISTRICT_SOURCE.exists():
            _empty_state("The district snapshot is not present in the workspace.")
        else:
            district = load_district_yields()
            states = sorted(district["State"].dropna().unique())
            state = st.selectbox("State", states, key="district_state")
            crop_options = sorted(district.loc[district["State"].eq(state), "Crop"].dropna().unique())
            crop = st.selectbox("Crop", crop_options, key="district_crop")
            subset = district.loc[district["State"].eq(state) & district["Crop"].eq(crop)]
            st.caption("Cross-sectional 2024–25 snapshot only; no district time-series volatility is inferred.")
            if "District" in subset:
                st.plotly_chart(px.bar(subset.sort_values("Yield", na_position="last"), x="District", y="Yield", title=f"{crop} yield by district", labels={"Yield": "Yield (Kg/Ha)"}), use_container_width=True)
            st.dataframe(subset, use_container_width=True, hide_index=True)

elif page == "AI/ML Insights":
    st.title("AI/ML Evaluation")
    st.caption("Chronological holdout results are compared with a previous-year baseline. These models estimate next-year yield from its historical lags; they do not establish causal drivers.")
    if historical.empty:
        _empty_state("No observations are available for model evaluation.")
    else:
        crop = st.selectbox("Crop", sorted(historical["Crop"].unique()), key="ml_crop")
        if st.button("Evaluate forecast models", type="primary"):
            result = evaluate_forecasts(historical, crop)
            if result["status"] != "evaluated":
                st.warning(f"Insufficient data: {result.get('observations', 0)} observations; minimum is {result.get('required', 20)}.")
            else:
                metric_frame = pd.DataFrame(result["metrics"]).T.reset_index(names="Model")
                st.write(f"Validation-selected model: **{result['selected_model']}**")
                st.dataframe(metric_frame, use_container_width=True, hide_index=True)
                st.caption(result["evaluation_design"])
                prediction = result["predictions"].melt(id_vars=["Year", "Actual"], var_name="Series", value_name="Yield")
                st.plotly_chart(px.line(prediction, x="Year", y="Yield", color="Series", markers=True, title=f"{crop}: holdout predictions and actuals"), use_container_width=True)
                importance = result.get("feature_importance") or {}
                if importance:
                    st.plotly_chart(px.bar(pd.DataFrame({"Feature": importance.keys(), "Importance": importance.values()}), x="Feature", y="Importance", title="Selected model feature importance"), use_container_width=True)
                st.warning("Feature importance describes model reliance, not causal influence. Check whether an ML model beats the baseline before preferring it.")

elif page == "Risk Intelligence":
    st.title("Downside Risk and Anomalies")
    if metrics.empty:
        _empty_state("No annual observations are available.")
    else:
        st.subheader("Largest negative trend deviations")
        risk = rank_crops(metrics)["downside_risk"]
        st.dataframe(risk, use_container_width=True, hide_index=True)
        if st.button("Detect unusual yield observations"):
            flagged = detect_yield_anomalies(historical)
            flagged = flagged.loc[flagged["Anomaly"]].sort_values("AnomalyScore") if not flagged.empty else flagged
            if flagged.empty:
                _empty_state("No observations were flagged at the configured contamination rate, or there were too few observations.")
            else:
                st.dataframe(flagged, use_container_width=True, hide_index=True)
                st.caption("Isolation Forest flags unusual fitted-trend residuals within each crop. Flags are screening signals, not evidence of a cause.")

else:
    st.title("Data Management and Reports")
    st.subheader("Persistent database")
    counts = store.counts()
    st.dataframe(pd.DataFrame([{"Table": name, "Rows": value} for name, value in counts.items()]), use_container_width=True, hide_index=True)
    st.caption(f"Seed source: {seed_status['source']}. Database retrieval is local and works offline.")

    with st.expander("Upload and validate CSV/XLSX"):
        uploaded = st.file_uploader("Dataset", type=["csv", "xlsx"])
        if uploaded:
            suffix = Path(uploaded.name).suffix.casefold()
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                temporary.write(uploaded.getvalue())
                temporary_path = Path(temporary.name)
            try:
                preview = load_table(temporary_path)
                st.write(f"Detected columns: {', '.join(map(str, preview.columns))}")
                st.dataframe(preview.head(8), use_container_width=True, hide_index=True)
                options = ["Automatic"] + list(map(str, preview.columns))
                with st.expander("Optional column mapping"):
                    mapping_fields = {}
                    for field in ("crop", "year", "yield", "season", "state", "district"):
                        choice = st.selectbox(f"{field.title()} column", options, key=f"map_{field}")
                        if choice != "Automatic":
                            mapping_fields[field] = choice
                requested_season = st.selectbox("Season to store", ["Total", "Kharif", "Rabi", "Summer", "All"], key="upload_season")
                unit = st.text_input("Yield unit", value="Kg/Ha", key="upload_unit")
                if st.button("Validate and store", type="primary"):
                    adapted = adapt_yield_data(preview, mapping_fields or None, yield_unit=unit)
                    clean = adapted.data
                    if "Season" in clean and requested_season != "All":
                        clean = select_season(clean, requested_season)
                    result = store.ingest_yields(
                        clean,
                        source_name=uploaded.name,
                        source_path=f"upload:{uploaded.name}",
                        source_type="upload",
                        reporting_status="user-uploaded; not independently verified",
                        default_unit=unit,
                    )
                    st.success(f"Stored {result['inserted']:,} new observations; {result['rows_seen']:,} valid rows were read. Layout: {adapted.detected_layout}.")
                    for issue in adapted.issues:
                        st.warning(issue)
                    st.rerun()
            except (ValueError, OSError) as error:
                st.error(str(error))
            finally:
                temporary_path.unlink(missing_ok=True)

    st.subheader("UPAg connection")
    st.caption("UPAg access requires approved userid/password credentials. No live response is simulated.")
    if st.button("Check UPAg access"):
        try:
            sources = UPAgClient().allowed_sources()
            st.success(f"Authenticated. Allowed source entries: {len(sources)}")
            st.json(sources)
        except UPAgAPIError as error:
            st.warning(str(error))

    if not metrics.empty:
        st.subheader("Export current national variability results")
        csv_bytes = metrics.to_csv(index=False).encode("utf-8")
        excel_stream = io.BytesIO()
        with pd.ExcelWriter(excel_stream, engine="openpyxl") as writer:
            metrics.to_excel(writer, index=False, sheet_name="Variability")
            historical.to_excel(writer, index=False, sheet_name="Annual yields")
        col1, col2, col3 = st.columns(3)
        col1.download_button("Download CSV", csv_bytes, "cropwise_variability.csv", "text/csv")
        col2.download_button("Download Excel", excel_stream.getvalue(), "cropwise_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        col3.download_button("Download PDF", _make_pdf(metrics, "Cropwise variability report"), "cropwise_variability.pdf", "application/pdf")