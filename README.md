# Financial Markets Data Platform

An end-to-end data engineering pipeline that ingests real-time stock prices and macroeconomic indicators, transforms them into analytics-ready models, and serves insights through a live dashboard.

## Architecture

Yahoo Finance API → Python Ingestion → BigQuery (raw layer)

FRED API         →                  ↓

dbt Transformations

↓

BigQuery (dbt_dev layer)

↓

Looker Studio Dashboard
All orchestrated by Apache Airflow — runs every weekday at 6am.

## Tech Stack

| Layer | Tool |
|---|---|
| Ingestion | Python, yfinance, fredapi |
| Storage | Google BigQuery |
| Transformation | dbt (dbt-bigquery) |
| Orchestration | Apache Airflow (Docker) |
| Serving | Looker Studio |

## Data Sources

**Yahoo Finance** — Daily OHLCV prices for SPY, AAPL, MSFT, TSLA, NVDA (1 year history)

**FRED API** — 5 macroeconomic indicators from 2020:
- Federal Funds Rate (DFF)
- Consumer Price Index (CPIAUCSL)
- Unemployment Rate (UNRATE)
- Yield Curve Spread (T10Y2Y)
- GDP (GDP)

> Note: all 5 indicators are ingested into the raw layer. The current mart surfaces 4 of them (fed funds rate, CPI, unemployment, yield curve spread); GDP is ingested but not yet pivoted into `mart_stock_macro_analysis`.

## Pipeline

### Ingestion
Two Python scripts land raw data into BigQuery's raw layer unchanged.
Raw data is append-only and immutable — if a transformation breaks downstream, data can be reprocessed without re-hitting the APIs.

### Transformation (dbt)
Three-layer transformation model:

- **Staging** — `stg_stock_prices`, `stg_macro_indicators` materialize as views. Clean column names, cast data types, remove nulls.
- **Marts** — `mart_stock_macro_analysis` materializes as a table. Calculates daily returns using a LAG window function, 30-day rolling average prices, and as-of joins the last-known macro values onto each trading day.

### Data Quality
7 dbt tests run after every transformation:
- Not-null checks on all key columns
- Accepted values check on ticker symbols

### Orchestration
Airflow DAG `market_data_pipeline` runs Monday–Friday at 6am:
ingest_stocks → ingest_fred → dbt run → dbt test

If any task fails, downstream tasks are skipped and the run is marked failed.

## Key Design Decisions

**Why append-only raw layer?**
Preserves full ingestion history. Enables reprocessing without API re-calls. Standard practice in production DE pipelines.

**Why dbt views for staging and tables for marts?**
Staging views have no storage cost and always reflect current raw data. Mart tables are pre-computed for fast dashboard queries.

**Why an as-of join for macro data?**
Stock prices are daily, while macro indicators are monthly or quarterly. An exact-date join would leave most trading days null, since a daily stock date rarely matches a monthly or quarterly observation date. Instead, each trading day is matched to the most recent macro observation on or before that date, resolved per series on the long (un-pivoted) macro table so a daily series can't blank out a monthly one. Every trading day therefore carries the last-known macro value rather than a null.

**Why separate ingestion scripts per source?**
Each source has independent failure modes. If Yahoo Finance is down, FRED ingestion still runs. Separation of concerns at the task level.

## Project Structure

├── ingestion/

│   ├── ingest_stocks.py       # Yahoo Finance ingestion

│   └── ingest_fred.py         # FRED macro ingestion

├── de/                        # dbt project

│   ├── models/

│   │   ├── staging/

│   │   │   ├── stg_stock_prices.sql

│   │   │   ├── stg_macro_indicators.sql

│   │   │   └── sources.yml

│   │   └── marts/

│   │       └── mart_stock_macro_analysis.sql

│   └── dbt_project.yml

├── airflow/

│   └── dags/

│       └── market_data_pipeline.py

└── requirements.txt

## Dashboard

Live Looker Studio dashboard built on top of `mart_stock_macro_analysis`:
- Stock price history with ticker filter
- Average daily returns by ticker
- Federal funds rate over time

[[Link to Dashboard](https://datastudio.google.com/s/h6DyKaUf8oY)]