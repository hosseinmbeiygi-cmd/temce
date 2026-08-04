"""Test parsing Codal Excel files - try different methods."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# Test with first file from آباد
base = "codal_excel_files/آباد"
files = sorted(os.listdir(base))
if not files:
    print("No files found")
    sys.exit(1)

fp = os.path.join(base, files[0])
print(f"Testing file: {fp}")
print(f"Size: {os.path.getsize(fp)} bytes")

# Method 1: Try read_excel
print("\n--- Method 1: pd.read_excel ---")
try:
    df = pd.read_excel(fp, header=None)
    print(f"SUCCESS! Shape: {df.shape}")
    print(f"Columns ({len(df.columns)} total): {list(df.columns)[:10]}")
    print("First 3 rows:")
    print(df.iloc[:3].to_string())
except Exception as e:
    print(f"FAILED: {e}")

# Method 2: Try read_html
print("\n--- Method 2: pd.read_html ---")
try:
    tables = pd.read_html(fp, header=None)
    print(f"SUCCESS! {len(tables)} tables found")
    df = tables[0]
    print(f"Shape: {df.shape}")
    print(f"Column types: {[type(c).__name__ for c in df.columns][:10]}")
    print("Columns (first 10):")
    for i, c in enumerate(df.columns[:10]):
        print(f"  Col {i}: type={type(c).__name__} value={str(c)[:100]}")
    print("\nFirst 3 rows:")
    print(df.iloc[:3].to_string())
except Exception as e:
    print(f"FAILED: {e}")
