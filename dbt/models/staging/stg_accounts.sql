select
    account_id,
    account_name,
    cast(signup_date as date)                      as signup_date,
    cast(date_trunc('month', cast(signup_date as date)) as date) as signup_month,
    company_size,
    industry,
    region,
    acquisition_channel,
    contract_type,
    initial_plan,
    initial_seats,
    cast(cac_usd as double)                        as cac_usd
from {{ source('landing', 'accounts') }}
