select
    event_id,
    account_id,
    cast(event_date as date)                      as event_date,
    cast(date_trunc('month', cast(event_date as date)) as date) as event_month,
    event_type,
    cast(mrr_before as double)                    as mrr_before,
    cast(mrr_after as double)                     as mrr_after,
    cast(mrr_after as double) - cast(mrr_before as double) as mrr_delta,
    plan,
    seats
from {{ source('landing', 'subscription_events') }}
