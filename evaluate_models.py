"""Run chronological crop forecast evaluation and print reproducible metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cropwise.ml import evaluate_forecasts
from cropwise.service import HISTORICAL_SOURCE, load_yield_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crop", default="Rice", help="Exact source crop label")
    parser.add_argument("--input", type=Path, default=HISTORICAL_SOURCE, help="CSV or XLSX dataset path")
    parser.add_argument("--output", type=Path, help="Optional JSON result path")
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()

    data = load_yield_file(args.input, annual_total=True, yield_unit="Kg/Ha")
    result = evaluate_forecasts(data, args.crop, test_fraction=args.test_fraction)
    if result["status"] != "evaluated":
        print(json.dumps(result, indent=2, default=str))
        return

    printable = {key: value for key, value in result.items() if key != "predictions"}
    print(f"Crop: {result['crop']}")
    print(f"Observations: {result['observations']} (features: {result['feature_observations']})")
    print(f"Chronological split: train={result['train_count']}, validation={result['validation_count']}, test={result['test_count']}")
    print(f"Validation-selected model: {result['selected_model']}")
    for model, metrics in result["metrics"].items():
        print(f"{model}: MAE={metrics['mae']:.3f}; RMSE={metrics['rmse']:.3f}; R2={metrics['r2']:.4f}")
    print(result["evaluation_design"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(printable, indent=2, default=str), encoding="utf-8")
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
