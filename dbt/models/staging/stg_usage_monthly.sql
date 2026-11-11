select
    account_id,
    cast(month as date)            as month,
    seats,
    active_users,
    seat_utilisation,
    features_adopted,
    logins,
    logins / nullif(seats, 0)      as logins_per_seat,
    cast(mrr as double)            as mrr
from {{ source('landing', 'usage_monthly') }}
