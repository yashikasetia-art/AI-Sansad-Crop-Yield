"""Generate competition presentation and PDF reports from current project data."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from cropwise.analysis import analyze_variability, rank_crops
from cropwise.ml import evaluate_forecasts
from cropwise.service import HISTORICAL_SOURCE, load_yield_file

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "outputs" / "generated"
NAVY = RGBColor(21, 50, 71)
TEAL = RGBColor(21, 123, 131)
GREEN = RGBColor(42, 118, 93)
PALE = RGBColor(239, 246, 242)
WHITE = RGBColor(255, 255, 255)
INK = RGBColor(31, 54, 65)


def add_text(slide, text, x, y, width, height, size=20, color=INK, bold=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    for index, line in enumerate(str(text).split("\n")):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.font.name = "Aptos"
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = color
        paragraph.space_after = Pt(8)
    return box


def base_slide(presentation, title):
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = PALE
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, presentation.slide_width, Inches(0.65))
    band.fill.solid()
    band.fill.fore_color.rgb = NAVY
    band.line.fill.background()
    add_text(slide, "CALYX  |  AI SANSAD 2026", 0.4, 0.12, 6, 0.3, 11, WHITE, True)
    add_text(slide, title, 0.55, 0.92, 12, 0.7, 28, NAVY, True)
    footer = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.55), Inches(7.08), Inches(12.1), Inches(0.035))
    footer.fill.solid()
    footer.fill.fore_color.rgb = TEAL
    footer.line.fill.background()
    return slide


def bullet_slide(presentation, title, items, note=None):
    slide = base_slide(presentation, title)
    add_text(slide, "\n".join("•  " + item for item in items), 0.75, 1.85, 11.8, 4.7, 20, INK)
    if note:
        add_text(slide, note, 0.78, 6.35, 11.5, 0.45, 11, GREEN, True)
    return slide


def table_slide(presentation, title, headers, rows, note=""):
    slide = base_slide(presentation, title)
    shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(0.65), Inches(1.9), Inches(12.0), Inches(min(4.65, (len(rows) + 1) * 0.43)))
    table = shape.table
    for column, value in enumerate(headers):
        table.cell(0, column).text = str(value)
    for row_index, values in enumerate(rows, start=1):
        for column, value in enumerate(values):
            table.cell(row_index, column).text = str(value)
    for row_index, row in enumerate(table.rows):
        for cell in row.cells:
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if row_index == 0 else (WHITE if row_index % 2 else PALE)
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.name = "Aptos"
                paragraph.font.size = Pt(10)
                paragraph.font.color.rgb = WHITE if row_index == 0 else INK
    if note:
        add_text(slide, note, 0.75, 6.4, 11.8, 0.4, 10, GREEN, True)
    return slide


def create_decks(history, metrics, forecast):
    deck = Presentation()
    deck.slide_width = Inches(13.333)
    deck.slide_height = Inches(7.5)
    cover = deck.slides.add_slide(deck.slide_layouts[6])
    cover.background.fill.solid()
    cover.background.fill.fore_color.rgb = NAVY
    stripe = cover.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(1.0), Inches(0.15), Inches(4.9))
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = TEAL
    stripe.line.fill.background()
    add_text(cover, "CROPWISE AI", 1.1, 1.5, 10.8, 0.8, 40, WHITE, True)
    add_text(cover, "India's crop yield stability & volatility intelligence", 1.12, 2.45, 10.5, 0.9, 24, RGBColor(177, 225, 209))
    add_text(cover, "AI Sansad 2026  |  CALYX  |  UG12Y3Q8\nAditya Jha, Team Leader", 1.15, 4.7, 10, 0.9, 16, WHITE)

    bullet_slide(deck, "The challenge", ["Compare crop yields across years and identify greater historical variability.", "Separate yield from production and cultivated area.", "Keep trend, variability, downside risk, and prediction distinct."])
    bullet_slide(deck, "Why variability matters", ["Averages can hide large year-to-year deviations.", "Relative spread helps compare crops with different yield scales.", "Historical patterns inform review; they do not prove causes."], "Decision support, not automated policy advice")
    table_slide(deck, "Supplied evidence", ["Dataset", "Coverage", "Use"], [
        ["National annual APY", f"{history['Year'].nunique()} crop years", "Annual yield; source Total rows"],
        ["State crop profile", "2021–22 to 2025–26", "Recent, incomplete comparison"],
        ["District APY", "2024–25", "Cross-section only"],
        ["Progressive Rabi area", "2026–27", "Area context, not yield"],
    ], "Eight CSV/XLSX files audited; a byte-identical state copy is not double-ingested.")
    bullet_slide(deck, "Data controls", ["Preserve missing values; never replace null with zero.", "Use source Total for annual values; do not sum seasons.", "Exclude aggregate categories from individual-crop rankings.", "Keep source, unit, period, and observation count visible."])
    bullet_slide(deck, "Working architecture", ["CSV/XLSX and optional UPAg → validation and schema adapter.", "SQLite provenance store → statistics and ML evaluation.", "FastAPI → Streamlit dashboard → CSV, Excel, and PDF exports.", "Offline dataset mode works without credentials or network access."])
    bullet_slide(deck, "Relative variability", ["Sample CV (%) = 100 × sample standard deviation / mean yield.", "CV is undefined for insufficient observations or non-positive mean.", "CV describes relative spread, not trend direction; trend slope is reported separately."])
    bullet_slide(deck, "Detrended variability", ["Fit an OLS linear trend against crop-year start.", "Residual = observed yield − fitted trend.", "Detrended CV = 100 × residual sample SD / mean observed yield.", "Do not divide by residual mean: residuals are centered near zero."])
    bullet_slide(deck, "Downside risk", ["Count negative residual years and report average and worst shortfall.", "Downside deviation = sqrt(mean(min(residual, 0)²)).", "Below −2 residual SD is a review flag, not a causal explanation."])
    bullet_slide(deck, "Classification", ["Stable/moderate/high labels use cohort 33rd/67th CV quantiles.", "Early/late residual SD flags changing volatility at a configurable default of 15%.", "These are analytical labels, not government categories.", "Continuous values remain visible beside every label."])

    ranks = rank_crops(metrics)
    rows = []
    for label, frame in (("Lower detrended CV", ranks.get("stable", pd.DataFrame()).head(5)), ("Higher detrended CV", ranks.get("variable", pd.DataFrame()).head(5))):
        for _, row in frame.iterrows():
            rows.append([label, row["Crop"], f"{row['MeanYield']:.0f}", f"{row['CVPercent']:.1f}%", f"{row['DetrendedCVPercent']:.1f}%", int(row["ObservationCount"])])
    table_slide(deck, "Observed crop comparison", ["Group", "Crop", "Mean Kg/Ha", "Raw CV", "Detrended CV", "n"], rows, "Computed from source Total series; rankings depend on coverage and cohort.")
    bullet_slide(deck, "State and season", ["Compare Kharif, Rabi, and Summer separately from Total.", "State data are recent and substantially incomplete.", "District data cover one year; no district volatility trend is claimed."])
    bullet_slide(deck, "Forecast design", ["Lagged yields, prior rolling mean, and time index predict next yield.", "Chronological train/validation/test ordering prevents future-to-past leakage.", "Random Forest and Gradient Boosting are compared with previous-year yield.", "Report MAE, RMSE, R², split sizes, and runtime."])
    if forecast.get("status") == "evaluated":
        score_rows = [[name, f"{values['mae']:.1f}", f"{values['rmse']:.1f}", f"{values['r2']:.3f}" if pd.notna(values["r2"]) else "NA"] for name, values in forecast["metrics"].items()]
        table_slide(deck, "Model evidence: Rice", ["Model", "MAE", "RMSE", "R²"], score_rows, f"Holdout n={forecast['test_count']}; validation-selected={forecast['selected_model']}.")
    else:
        bullet_slide(deck, "Model evidence", ["Insufficient observations for a defensible forecast.", "The system reports the limitation rather than forcing predictions."])
    bullet_slide(deck, "Explainable screening", ["Feature importance shows model reliance, not causal influence.", "Isolation Forest screens unusual trend residuals.", "K-Means groups standardized descriptive profiles for exploration."])
    bullet_slide(deck, "Prototype and impact", ["Interactive local dashboard with SQLite persistence and API.", "Upload unfamiliar CSV/XLSX with optional column mapping.", "Feasible as a no-paid-service research prototype; supports review, not automated intervention."])
    bullet_slide(deck, "Limitations and next work", ["Verify source revisions, zero semantics, and provisional reporting status.", "Compare robust detrending and structural-break methods.", "Broaden rolling-origin tests and add covariates only with a defensible design.", "Complete live UPAg extraction when approved credentials are available."])
    bullet_slide(deck, "Build the model. Defend the logic. Prove the results.", ["Cropwise makes crop-yield comparisons reproducible and interpretable.", "Prefer the model supported by honest validation, including a simple baseline."], "CALYX  |  AI Sansad 2026")
    deck.save(OUTPUT / "ROUND_1_PRESENTATION.pptx")

    short = Presentation()
    short.slide_width = Inches(13.333)
    short.slide_height = Inches(7.5)
    bullet_slide(short, "Cropwise AI | CALYX", ["India's crop-yield stability and volatility intelligence", "AI Sansad 2026 | UG12Y3Q8"])
    bullet_slide(short, "Question and evidence", ["Compare annual yield variability.", "Use source Total rows; preserve missingness; exclude aggregates.", "Limit state and district claims to actual source coverage."])
    bullet_slide(short, "Statistical engine", ["Sample CV measures relative dispersion.", "OLS detrending separates trend from residual variation.", "Downside metrics and cohort labels support review, not causal claims."])
    bullet_slide(short, "ML discipline", ["Use chronological splits and a previous-year baseline.", "Report actual holdout results; a simple baseline can win.", "Do not force a prediction for short series."])
    bullet_slide(short, "Prototype and close", ["Offline SQLite, FastAPI, Streamlit, and exports.", "Next: validate live sources and broaden out-of-sample evaluation.", "Transparent evidence before automated recommendations."])
    short.save(OUTPUT / "ROUND_1_5_MIN.pptx")


def clean_markdown(text):
    for line in text.splitlines():
        if line.startswith("```") or line.startswith("|") or line.startswith("---"):
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*]\s+", "- ", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"`([^`]+)`", r"\1", line)
        if line.strip():
            yield line


def write_pdf(output_path, title, source_names):
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("Section", parent=styles["Heading2"], textColor=colors.HexColor("#153247"), spaceBefore=8, spaceAfter=5)
    body = ParagraphStyle("BodySmall", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12, spaceAfter=4)
    story = [Paragraph(title, styles["Title"]), Spacer(1, 5 * mm)]
    for name in source_names:
        path = ROOT / name
        if not path.exists():
            continue
        story.append(Paragraph(path.stem.replace("_", " "), heading))
        for line in clean_markdown(path.read_text(encoding="utf-8")):
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe, body))
    SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=17 * mm, leftMargin=17 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=title).build(story)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    history = load_yield_file(HISTORICAL_SOURCE, annual_total=True, yield_unit="Kg/Ha")
    metrics = analyze_variability(history)
    forecast = evaluate_forecasts(history, "Rice")
    create_decks(history, metrics, forecast)
    write_pdf(OUTPUT / "ROUND_1_ABSTRACT.pdf", "Cropwise AI Abstract", ["ABSTRACT.md", "PROBLEM_STATEMENT.md"])
    write_pdf(OUTPUT / "FINAL_PROJECT_REPORT.pdf", "Cropwise AI Final Project Report", ["README.md", "ABSTRACT.md", "PROBLEM_STATEMENT.md", "METHODOLOGY.md", "SYSTEM_ARCHITECTURE.md", "DATA_DICTIONARY.md", "DATA_AUDIT_REPORT.md", "MODEL_EVALUATION_REPORT.md", "LIMITATIONS_AND_FUTURE_SCOPE.md", "REFERENCES.md"])
    write_pdf(OUTPUT / "TECHNICAL_DEBATE_HANDBOOK.pdf", "Cropwise AI Technical Debate Handbook", ["TECHNICAL_DEBATE_HANDBOOK.md"])
    write_pdf(OUTPUT / "QUICK_EXECUTION_GUIDE.pdf", "Cropwise AI Quick Execution Guide", ["ROUND_2_QUICK_GUIDE.md", "DEMO_SCRIPT.md"])
    print(f"Generated presentation, short deck, and four PDF files in {OUTPUT.relative_to(ROOT)}")
    print(f"Annual rows: {len(history)}; metric rows: {len(metrics)}; Rice model status: {forecast['status']}")


if __name__ == "__main__":
    main()
