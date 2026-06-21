with source as (
    select * from {{ source('raw', 'macro_indicators') }}
),

cleaned as (
    select
        -- Identifiers
        series_id,
        series_name,

        -- Timestamps
        cast(date as date)             as observation_date,
        cast(ingested_at as timestamp) as ingested_at,

        -- Value rounded to 3 decimal places
        -- Macro indicators need more precision than stock prices
        -- GDP in billions, rates as percentages
        round(cast(value as float64), 3) as indicator_value

    from source
    where value is not null
)

select * from cleaned