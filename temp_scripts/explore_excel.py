import pandas as pd

print("=== facts_raw.xlsx ===")
df1 = pd.read_excel('output/facts_raw.xlsx')
print(f"Records: {len(df1)}")
print(f"Columns: {df1.columns.tolist()}")
if 'ticker' in df1.columns:
    print(f"Tickers: {df1['ticker'].nunique()}")
    print(f"Ticker list: {df1['ticker'].unique().tolist()}")

print("\n=== validation_report.xlsx ===")
xl = pd.ExcelFile('output/validation_report.xlsx')
print(f"Sheets: {xl.sheet_names}")
for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet)
    print(f"\n{sheet}: {len(df)} rows, {len(df.columns)} cols")
    print(f"  Columns: {df.columns.tolist()[:5]}...")