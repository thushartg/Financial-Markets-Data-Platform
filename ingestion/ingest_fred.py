import pandas as pd
from fredapi import Fred
from google.cloud import bigquery
from datetime import datetime, timezone
import os

# ── CONFIG ──────────────────────────────────────
PROJECT_ID = "market-data-platform-500016"
DATASET_ID = "raw"
TABLE_ID   = "macro_indicators"

# FRED series IDs → human readable names
# These are the macro forces that move markets
SERIES = {
    "DFF":     "federal_funds_rate",
    "CPIAUCSL":"consumer_price_index",
    "UNRATE":  "unemployment_rate",
    "T10Y2Y":  "yield_curve_spread",
    "GDP":     "gross_domestic_product"
}
# ────────────────────────────────────────────────

def fetch_macro_data(series: dict, start_date: str = "2020-01-01") -> pd.DataFrame:
    # Reads your API key from the environment variable
    # Never pass the key directly — always read from environment
    fred = Fred(api_key=os.environ["FRED_API_KEY"])

    all_data = []

    for series_id, series_name in series.items():
        # FRED returns a pandas Series object — index is date, values are numbers
        raw = fred.get_series(series_id, observation_start=start_date)

        # Convert to DataFrame so we can add columns
        df = raw.reset_index()
        df.columns = ["date", "value"]

        # Tag each row with both the ID and human readable name
        # series_id = "DFF", series_name = "federal_funds_rate"
        # You'll want both in BigQuery for filtering
        df["series_id"]   = series_id
        df["series_name"] = series_name

        # FRED has gaps in data — GDP is quarterly, others are monthly or daily
        # dropna removes rows where no observation was recorded
        # Real DE pipelines always handle nulls explicitly — never silently
        df = df.dropna(subset=["value"])

        all_data.append(df)
        print(f"  Fetched {len(df)} rows for {series_name}")

    combined = pd.concat(all_data, ignore_index=True)
    combined["ingested_at"] = datetime.now(timezone.utc)

    return combined

def load_to_bigquery(df: pd.DataFrame) -> None:
    client = bigquery.Client(project=PROJECT_ID)

    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        autodetect=True,
    )

    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()

    print(f"Loaded {len(df)} rows into {table_ref}")
    print(f"Series: {df['series_name'].unique().tolist()}")
    print(f"Date range: {df['date'].min()} → {df['date'].max()}")


if __name__ == "__main__":
    print("Fetching macro data from FRED...")
    df = fetch_macro_data(SERIES)
    print(f"\nTotal rows fetched: {len(df)}\n")
    print(df.groupby("series_name")[["date", "value"]].tail(2))

    print("\nLoading to BigQuery...")
    load_to_bigquery(df)
    print("\nDone.")