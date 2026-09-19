"""
01_extract.py
Reads all eight SAP source sheets from the Excel workbook and saves each
as a raw CSV in data/processed/. This is the entry point of the pipeline.

Run:
    python src/01_extract.py
"""
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE_FILE = BASE_DIR / "data" / "raw" / "SAP-DataSet.xlsx"
OUTPUT_DIR = BASE_DIR / "data" / "processed"

# Confirmed by inspecting the actual workbook (not assumed)
SHEETS = ["KNA1", "LFA1", "VBAK", "VBAP", "LIKP", "LIPS", "VTTK", "VTTP"]


def extract_data():
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Source file not found at {SOURCE_FILE}. "
            "Place SAP-DataSet.xlsx in data/raw/ before running."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    extracted = {}

    for sheet in SHEETS:
        df = pd.read_excel(SOURCE_FILE, sheet_name=sheet)
        df.columns = df.columns.astype(str).str.strip()
        extracted[sheet] = df
        df.to_csv(OUTPUT_DIR / f"{sheet}.csv", index=False)
        print(f"{sheet}: {len(df)} rows, {len(df.columns)} columns")

    return extracted


if __name__ == "__main__":
    extract_data()
