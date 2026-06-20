import yfinance as yf
import pandas as pd
from google.cloud import bigquery
from datetime import datetime

# ── CONFIG ──────────────────────────────────────
PROJECT_ID = "market-data-platform-500016" 
DATASET_ID = "raw"
TABLE_ID   = "stock_prices"

TICKERS = ["SPY", "AAPL", "MSFT", "TSLA", "NVDA"]
# ────────────────────────────────────────────────

def fetch_stock_data(tickers: list, period: str = "1y") -> pd.DataFrame:
    all_data = []

    for ticker in tickers:
        # yfinance hits Yahoo Finance and returns daily OHLCV bars
        # OHLCV = Open, High, Low, Close, Volume
        # auto_adjust handles stock splits automatically
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)

        # Without this line, after concat you'd have 1000 rows
        # with no idea which price belongs to which company
        df["ticker"] = ticker

# yfinance 1.4.1+ returns MultiIndex columns like ('Close', 'AAPL')
        # We grab only the first element of the tuple — the price type
        # BEFORE we do anything else with the DataFrame
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0].lower().replace(" ", "_") for col in df.columns]
        else:
            df.columns = [col.lower().replace(" ", "_") for col in df.columns]

        df["ticker"] = ticker
        df.reset_index(inplace=True)

        all_data.append(df)

    combined = pd.concat(all_data, ignore_index=True)

    # Date column name comes through cleanly now — just lowercase it
    combined.columns = [col.lower().replace(" ", "_") for col in combined.columns]

    # This timestamp tells you WHEN this row entered your pipeline
    # Critical for debugging — "was this data from today's run or yesterday's?"
    combined["ingested_at"] = datetime.now(datetime.UTC)

    return combined

def load_to_bigquery(df: pd.DataFrame) -> None:
    # This line finds your credentials automatically
    # from the environment variable you set earlier
    client = bigquery.Client(project=PROJECT_ID)

    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    job_config = bigquery.LoadJobConfig(
        # APPEND = add new rows to existing data
        # TRUNCATE = wipe everything and replace
        # NEVER use TRUNCATE on a raw layer — you lose history
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,

        # BigQuery figures out column types from your data
        # Fine for now — in production you'd define this explicitly
        autodetect=True,
    )

    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)

    # This line WAITS for BigQuery to finish
    # Without it your script exits before the data actually lands
    job.result()

    print(f"Loaded {len(df)} rows into {table_ref}")
    print(f"Tickers: {df['ticker'].unique().tolist()}")
    print(f"Date range: {df['date'].min()} → {df['date'].max()}")

if __name__ == "__main__":
    print("Fetching stock data...")
    df = fetch_stock_data(TICKERS)
    print(f"Fetched {len(df)} rows\n")
    print(df[["date", "ticker", "close", "volume", "ingested_at"]].head(10))

    print("\nLoading to BigQuery...")
    load_to_bigquery(df)
    print("\nDone.")