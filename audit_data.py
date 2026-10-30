"""Audit the supplied agricultural datasets without modifying source files."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "DATA_AUDIT_REPORT.md"
IDENTIFIER_COLUMNS = ("Crop", "State", "District", "Season", "Year")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_xlsx(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    workbook = pd.ExcelFile(path)
    if not workbook.sheet_names:
        raise ValueError("Workbook has no worksheets")

    sheet_name = workbook.sheet_names[0]
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
    header_row = None
    for row_index, row in raw.iterrows():
        values = {str(value).strip().casefold() for value in row.dropna()}
        if "year" in values and "season" in values:
            header_row = int(row_index)
            break
    if header_row is None:
        raise ValueError("Could not locate a header row containing Year and Season")

    frame = pd.read_excel(path, sheet_name=sheet_name, header=[header_row - 1, header_row])
    flattened: list[str] = []
    for parent, child in frame.columns:
        parent_text = str(parent).strip()
        child_text = str(child).strip()
        if parent_text.startswith("Unnamed:"):
            flattened.append(child_text)
        else:
            flattened.append(f"{parent_text}-{child_text}")
    frame.columns = flattened

    if "Year" in frame.columns:
        frame["Year"] = frame["Year"].ffill()
    season_column = next((column for column in frame if column.casefold() == "season"), None)
    blank_rows = int(frame[season_column].isna().sum()) if season_column else 0
    if season_column:
        frame = frame.loc[frame[season_column].notna()].copy()

    return frame, {
        "sheet": sheet_name,
        "metadata_rows_before_header": header_row - 1,
        "header_rows": [header_row - 1, header_row],
        "blank_rows_removed_from_analysis": blank_rows,
    }


def read_dataset(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    if path.suffix.casefold() == ".xlsx":
        return _read_xlsx(path)
    return pd.read_csv(path, low_memory=False), {}


def _key_duplicates(frame: pd.DataFrame) -> int | None:
    if {"Crop", "State", "District", "Season"}.issubset(frame.columns):
        keys = ["Crop", "State", "District", "Season"]
    elif {"Crop", "State", "Season"}.issubset(frame.columns):
        keys = ["Crop", "State", "Season"]
    elif {"Crop", "Season"}.issubset(frame.columns):
        keys = ["Crop", "Season"]
    elif {"Year", "Season"}.issubset(frame.columns):
        keys = ["Year", "Season"]
    else:
        return None
    return int(frame.duplicated(keys).sum())


def inspect(path: Path) -> dict[str, Any]:
    frame, workbook_info = read_dataset(path)
    numeric = frame.select_dtypes(include="number")
    categories: dict[str, list[str]] = {}
    for column in IDENTIFIER_COLUMNS:
        if column in frame.columns:
            values = frame[column].dropna().astype(str).str.strip()
            categories[column] = sorted(values.unique().tolist())

    missing = {str(column): int(count) for column, count in frame.isna().sum().items() if count}
    zeros = {str(column): int((numeric[column] == 0).sum()) for column in numeric if (numeric[column] == 0).any()}
    negatives = {str(column): int((numeric[column] < 0).sum()) for column in numeric if (numeric[column] < 0).any()}
    yield_columns = [column for column in frame.columns if "yield" in str(column).casefold()]
    yield_zeros = {
        str(column): int((pd.to_numeric(frame[column], errors="coerce") == 0).sum())
        for column in yield_columns
        if (pd.to_numeric(frame[column], errors="coerce") == 0).any()
    }
    yield_negatives = {
        str(column): int((pd.to_numeric(frame[column], errors="coerce") < 0).sum())
        for column in yield_columns
        if (pd.to_numeric(frame[column], errors="coerce") < 0).any()
    }

    return {
        "name": path.name,
        "sha256": sha256(path),
        "rows": int(len(frame)),
        "columns_count": int(len(frame.columns)),
        "columns": [str(column) for column in frame.columns],
        "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
        "missing": missing,
        "duplicate_rows": int(frame.duplicated().sum()),
        "duplicate_keys": _key_duplicates(frame),
        "categories": categories,
        "zero_numeric": zeros,
        "negative_numeric": negatives,
        "zero_yields": yield_zeros,
        "negative_yields": yield_negatives,
        "workbook": workbook_info,
    }


def _format_mapping(mapping: dict[str, Any]) -> str:
    if not mapping:
        return "None"
    return "; ".join(f"`{key}`: {value}" for key, value in mapping.items())


def create_report(inventory: list[dict[str, Any]]) -> str:
    lines = [
        "# Dataset Audit Report",
        "",
        "Generated by `audit_data.py`. Source files are read-only; the workbook is parsed with its two-row crop/measure header and merged year labels forward-filled for analysis.",
        "",
        "## Workspace Inventory",
        "",
        "| File | Records | Columns | Exact duplicate rows | Duplicate keys |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in inventory:
        key_duplicates = "Not applicable" if item["duplicate_keys"] is None else str(item["duplicate_keys"])
        lines.append(
            f"| `{item['name']}` | {item['rows']:,} | {item['columns_count']} | "
            f"{item['duplicate_rows']:,} | {key_duplicates} |"
        )

    lines.extend(
        [
            "",
            "## File-Level Findings",
            "",
        ]
    )
    for item in inventory:
        lines.extend(
            [
                f"### `{item['name']}`",
                "",
                f"- SHA-256: `{item['sha256']}`",
                f"- Columns and inferred types: {_format_mapping(item['dtypes'])}",
                f"- Missing values: {_format_mapping(item['missing'])}",
                f"- Numeric zero counts: {_format_mapping(item['zero_numeric'])}",
                f"- Numeric negative counts: {_format_mapping(item['negative_numeric'])}",
                f"- Yield zero counts: {_format_mapping(item['zero_yields'])}",
                f"- Yield negative counts: {_format_mapping(item['negative_yields'])}",
            ]
        )
        if item["workbook"]:
            details = item["workbook"]
            lines.append(
                f"- Workbook layout: sheet `{details['sheet']}`, metadata rows before header "
                f"`{details['metadata_rows_before_header']}`, header rows `{details['header_rows']}`, "
                f"blank analysis rows excluded `{details['blank_rows_removed_from_analysis']}`."
            )
        for column, values in item["categories"].items():
            lines.append(f"- Distinct `{column}` values ({len(values)}): {', '.join(values)}")
        lines.append("")

    identical_groups: dict[str, list[str]] = {}
    for item in inventory:
        identical_groups.setdefault(item["sha256"], []).append(item["name"])
    identical_groups = {digest: names for digest, names in identical_groups.items() if len(names) > 1}
    lines.extend(["## Interpretation and Data Handling", ""])
    if identical_groups:
        for names in identical_groups.values():
            lines.append(f"- Byte-identical files: {', '.join(f'`{name}`' for name in names)}. Ingest only one copy.")
    else:
        lines.append("- No byte-identical dataset files were found.")
    lines.extend(
        [
            "- The all-India year-wise file is the long-term source. Its `Total` season rows represent annual values; seasonal rows must not be added to them.",
            "- The state-wise files are short recent panels with substantial missingness, especially for 2025–26. Missing observations remain missing and are never converted to zero.",
            "- The district file contains only 2024–25 and supports cross-sectional comparisons, not historical district volatility claims.",
            "- The progressive Rabi report measures area sown, not yield, and is contextual only.",
            "- Aggregate categories (for example cereals, total pulses, and total food grains) are not individual crops and must be excluded from crop-level rankings.",
            "- The workbook explicitly identifies DA&FW as the source and reports area in lakh hectares, production in lakh tonnes, and yield in Kg/Ha. The CSV extracts do not carry estimation-status fields; the status of 2025–26 values is therefore unverified here.",
            "- Zero and negative values are surfaced rather than silently altered. Negative progressive-area differences represent decreases; they are not invalid yields. Yield zeroes require source-context review before treating them as observations or missing values.",
            "- Crop labels are reported exactly as supplied. Similar-looking labels are not merged unless a reviewed alias mapping establishes equivalence.",
            "",
            "## Source Documentation",
            "",
            "- UPAg portal: https://www.upag.gov.in/",
            "- UPAg API OpenAPI: https://data.upag.gov.in/api/v1/openapi.json",
            "- Workbook attribution: DA&FW, as printed in the workbook metadata.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    paths = sorted(
        path for path in ROOT.iterdir()
        if path.suffix.casefold() in {".csv", ".xlsx"}
    )
    inventory = [inspect(path) for path in paths]
    report = create_report(inventory)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Audited {len(inventory)} datasets; report: {REPORT_PATH.name}")
    for item in inventory:
        print(
            f"{item['name']}: {item['rows']} rows x {item['columns_count']} columns; "
            f"missing cells={sum(item['missing'].values())}; duplicates={item['duplicate_rows']}"
        )


if __name__ == "__main__":
    main()