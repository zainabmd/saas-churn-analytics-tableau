-- Dense account x month spine from signup to the as-of month. Months without billed usage carry
-- MRR = 0, so churn and reactivation show up as transitions between consecutive rows.
with months as (
    select cast(m as date) as month
    from range(date '2022-01-01', cast('{{ var("as_of_month") }}' as date) + interval 1 month, interval 1 month) t(m)
),
spine as (
    select a.account_id, m.month
    from {{ ref('stg_accounts') }} a
    join months m on m.month >= a.signup_month
),
joined as (
    select
        s.account_id,
        s.month,
        coalesce(u.mrr, 0)   as mrr,
        coalesce(u.seats, 0) as seats,
        u.active_users,
        u.seat_utilisation,
        u.features_adopted,
        u.logins,
        u.logins_per_seat
    from spine s
    left join {{ ref('stg_usage_monthly') }} u
        on u.account_id = s.account_id and u.month = s.month
)
select
    *,
    mrr > 0                                             as is_active,
    coalesce(lag(mrr) over w, 0)                        as prev_mrr,
    -- has the account ever paid before this month? (separates "new" from "reactivation")
    coalesce(max(case when mrr > 0 then 1 else 0 end) over (
        partition by account_id order by month rows between unbounded preceding and 1 preceding), 0) = 1
                                                        as was_ever_active
from joined
window w as (partition by account_id order by month)
