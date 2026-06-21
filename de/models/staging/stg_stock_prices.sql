with source as (
    select * from {{ source('raw', 'stock_prices') }}
),

cleaned as (
    select
        -- Identifiers
        ticker,
        
        -- Timestamps
        cast(date as date)                          as price_date,
        cast(ingested_at as timestamp)              as ingested_at,
        
        -- Prices rounded to 2 decimal places
        -- Raw data comes in with 15 decimal places — meaningless precision
        round(cast(open as float64), 2)             as open_price,
        round(cast(high as float64), 2)             as high_price,
        round(cast(low as float64), 2)              as low_price,
        round(cast(close as float64), 2)            as close_price,
        
        -- Volume as integer — no decimals on share counts
        cast(volume as int64)                       as volume

    from source
    where close is not null  -- remove rows with no closing price
)

select * from cleaned