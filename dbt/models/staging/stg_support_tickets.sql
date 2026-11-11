select
    ticket_id,
    account_id,
    cast(opened_at as date)                        as opened_at,
    cast(date_trunc('month', cast(opened_at as date)) as date) as opened_month,
    severity,
    category,
    resolution_hours,
    csat
from {{ source('landing', 'support_tickets') }}
