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

        -- 30 day rolling average price
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

-- Macro indicators in LONG form (no pivot yet).
-- Keeping each series as its own rows means they resolve independently
-- in the as-of join below — a daily series can't blank out a monthly one.
macro_long as (
    select
        series_name,
        observation_date,
        indicator_value
    from {{ ref('stg_macro_indicators') }}
),

-- As-of join: for each (ticker, trading day, series), take the most recent
-- macro observation ON OR BEFORE that trading day. This carries the
-- last-known value forward across non-observation days, instead of leaving
-- nulls when a stock date doesn't exactly match a macro observation date.
resolved as (
    select
        s.ticker,
        s.price_date,
        s.close_price,
        s.previous_close,
        s.daily_return_pct,
        s.rolling_30d_avg_price,
        ml.series_name,
        ml.indicator_value
    from stock_returns s
    left join macro_long ml
        on ml.observation_date <= s.price_date
    qualify row_number() over (
        partition by s.ticker, s.price_date, ml.series_name
        order by ml.observation_date desc
    ) = 1
),

-- Pivot the resolved series back into one row per ticker/day,
-- with each macro indicator as its own column.
final as (
    select
        ticker,
        price_date,
        close_price,
        previous_close,
        daily_return_pct,
        rolling_30d_avg_price,

        max(case when series_name = 'federal_funds_rate'   then indicator_value end) as fed_funds_rate,
        max(case when series_name = 'consumer_price_index' then indicator_value end) as cpi,
        max(case when series_name = 'unemployment_rate'    then indicator_value end) as unemployment_rate,
        max(case when series_name = 'yield_curve_spread'   then indicator_value end) as yield_curve_spread

    from resolved
    -- Remove each ticker's first day (daily_return is null there)
    where previous_close is not null
    group by
        ticker, price_date, close_price, previous_close,
        daily_return_pct, rolling_30d_avg_price
)

select * from final