with stock_returns as (
    select
        ticker,
        price_date,
        close_price,

        -- LAG looks one row above, partitioned by ticker
        -- so AAPL only looks at previous AAPL row, never SPY
        lag(close_price, 1) over (
            partition by ticker
            order by price_date
        ) as previous_close,

        -- Daily return percentage
        -- Will be null for first row of each ticker (no previous row)
        round(
            (close_price - lag(close_price, 1) over (
                partition by ticker order by price_date
            )) / lag(close_price, 1) over (
                partition by ticker order by price_date
            ) * 100
        , 2) as daily_return_pct,

        -- 30 day rolling average return
        -- avg() over a window of last 30 rows per ticker
        round(
            avg(close_price) over (
                partition by ticker
                order by price_date
                rows between 29 preceding and current row
            )
        , 2) as rolling_30d_avg_price

    from {{ ref('stg_stock_prices') }}
),

-- Pivot macro indicators so each date has one row
-- with all macro values as columns
macro as (
    select
        observation_date,
        -- Pull each series into its own column
        max(case when series_name = 'federal_funds_rate'  then indicator_value end) as fed_funds_rate,
        max(case when series_name = 'consumer_price_index' then indicator_value end) as cpi,
        max(case when series_name = 'unemployment_rate'   then indicator_value end) as unemployment_rate,
        max(case when series_name = 'yield_curve_spread'  then indicator_value end) as yield_curve_spread

    from {{ ref('stg_macro_indicators') }}
    group by observation_date
),

-- Join stock returns with macro conditions on the same date
final as (
    select
        s.ticker,
        s.price_date,
        s.close_price,
        s.previous_close,
        s.daily_return_pct,
        s.rolling_30d_avg_price,

        -- Macro conditions on that date
        m.fed_funds_rate,
        m.cpi,
        m.unemployment_rate,
        m.yield_curve_spread

    from stock_returns s
    left join macro m
        on s.price_date = m.observation_date

    -- Remove first row of each ticker since daily_return is null there
    where s.previous_close is not null
)

select * from final