select
    account_id,
    cast(responded_at as date)                      as responded_at,
    cast(date_trunc('month', cast(responded_at as date)) as date) as responded_month,
    score,
    case when score >= 9 then 'Promoter' when score >= 7 then 'Passive' else 'Detractor' end as nps_category
from {{ source('landing', 'nps_responses') }}
