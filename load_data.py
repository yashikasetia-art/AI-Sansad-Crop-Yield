
import pandas as pd
import os

# Folder containing all CSV files
folder = os.path.dirname(os.path.abspath(__file__))

# Load the state-wise dataset
state_file = [
    f for f in os.listdir(folder)
    if "State-wise" in f and f.endswith(".csv")
][0]

df = pd.read_csv(os.path.join(folder, state_file))

print("\n========== DATASET OVERVIEW ==========")

print("Total Rows:", len(df))
print("Total Columns:", len(df.columns))
print("Duplicate Rows:", df.duplicated().sum())

print("\n========== MISSING VALUES ==========")

print(df.isnull().sum())

# Missing values year-wise
print("\n========== YEAR-WISE MISSING DATA ==========")

years = ["2021-22", "2022-23", "2023-24",
         "2024-25", "2025-26"]

for year in years:
    print("\nYear:", year)

    for variable in ["Area", "Production", "Yield"]:
        col = variable + "-" + year
        print(variable, ":", df[col].isnull().sum())

# Season-wise missing records
print("\n========== SEASON-WISE MISSING DATA ==========")

print(df[df.isnull().any(axis=1)].groupby("Season").size())

# Exact crop names
print("\n========== ALL UNIQUE CROP NAMES ==========")

crop_names = sorted(df["Crop"].dropna().unique())

for crop in crop_names:
    print(crop)

print("\nTotal Unique Crops:", len(crop_names))

# Selected crops availability
selected_crops = [
    "Wheat",
    "Rice",
    "Maize",
    "Gram",
    "Chickpea",
    "Sugarcane",
    "Cotton",
    "Soybean",
    "Mustard"
]

print("\n========== CROP AVAILABILITY ==========")

seasonal_df = df[df["Season"] != "Total"]

for crop in selected_crops:

    crop_data = seasonal_df[
        seasonal_df["Crop"].str.lower() == crop.lower()
    ]

    print("\nCrop:", crop)
    print("Total Records:", len(crop_data))

    for year in years:
        col = "Yield-" + year
        available = crop_data[col].notna().sum()

        print(year, "Available Yield:", available)

# Save crop names into a text file
with open(os.path.join(folder, "crop_names.txt"), "w") as f:
    for crop in crop_names:
        f.write(crop + "\n")

print("\n========== ANALYSIS COMPLETE ==========")
print("Crop names saved in crop_names.txt")

