import unittest

import numpy as np
import pandas as pd

from cropwise.analysis import analyze_variability, annual_yield_changes
from cropwise.dataset_adapter import adapt_yield_data, select_season


class DatasetAdapterTests(unittest.TestCase):
    def test_wide_annual_source_uses_total_rows_and_preserves_missing(self):
        source = pd.DataFrame(
            {
                "Year": ["2020-21", "2020-21", "2021-22", "2021-22"],
                "Season": ["Kharif", "Total", "Kharif", "Total"],
                "Rice-Yield": [10, 11, 12, 13],
            }
        )
        adapted = adapt_yield_data(source)
        annual = select_season(adapted.data)
        self.assertEqual(annual["Yield"].tolist(), [11, 13])
        self.assertEqual(adapted.detected_layout, "crop-metric-wide")

    def test_long_column_mapping_and_missing_values(self):
        source = pd.DataFrame({"item": [" Rice ", "Wheat"], "crop_year": [2020, 2021], "value": [2.0, np.nan]})
        adapted = adapt_yield_data(source, {"crop": "item", "year": "crop_year", "yield": "value"})
        self.assertEqual(len(adapted.data), 1)
        self.assertEqual(adapted.data.iloc[0]["Crop"], "Rice")
        self.assertTrue(adapted.issues)

    def test_annual_selector_refuses_to_combine_seasons(self):
        source = pd.DataFrame({"Crop": ["Rice"], "Year": [2020], "Season": ["Kharif"], "Yield": [4]})
        with self.assertRaisesRegex(ValueError, "Total observations"):
            select_season(source)


class VariabilityTests(unittest.TestCase):
    def test_cv_and_detrended_cv(self):
        source = pd.DataFrame({"Crop": ["Rice"] * 5, "Year": [str(year) for year in range(2000, 2005)], "Yield": [100, 110, 120, 130, 140]})
        result = analyze_variability(source).iloc[0]
        expected_cv = np.std([100, 110, 120, 130, 140], ddof=1) / 120 * 100
        self.assertAlmostEqual(result["CVPercent"], expected_cv)
        self.assertAlmostEqual(result["DetrendedCVPercent"], 0.0, places=8)
        self.assertEqual(result["TrendDirection"], "Increasing")

    def test_change_with_zero_previous_yield_is_missing(self):
        source = pd.DataFrame({"Crop": ["Rice"] * 2, "Year": ["2000", "2001"], "Yield": [0, 3]})
        changes = annual_yield_changes(source)
        self.assertTrue(np.isnan(changes.iloc[1]["AnnualChangePct"]))

    def test_change_across_missing_calendar_year_is_not_reported_as_annual(self):
        source = pd.DataFrame({"Crop": ["Rice"] * 2, "Year": ["2000", "2002"], "Yield": [100, 130]})
        changes = annual_yield_changes(source)
        self.assertTrue(np.isnan(changes.iloc[1]["AnnualChange"]))
        self.assertTrue(np.isnan(changes.iloc[1]["AnnualChangePct"]))

    def test_aggregate_and_duplicate_years_are_not_ranked(self):
        source = pd.DataFrame({"Crop": ["Total Pulses"] * 2, "Year": ["2000", "2001"], "Yield": [2, 3]})
        self.assertTrue(analyze_variability(source).empty)
        duplicated = pd.DataFrame({"Crop": ["Rice"] * 2, "Year": ["2000", "2000"], "Yield": [2, 3]})
        with self.assertRaisesRegex(ValueError, "Duplicate crop/year"):
            analyze_variability(duplicated)


if __name__ == "__main__":
    unittest.main()