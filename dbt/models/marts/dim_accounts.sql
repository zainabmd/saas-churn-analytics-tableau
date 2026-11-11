-- Account dimension with lifecycle and current-state attributes (as of the as-of month).
with life as (
    select
        account_id,
        min(case when is_active then month end) as first_paid_month,
        max(case when is_active then month end) as last_paid_month,
        count(*) filter (where is_active)       as active_months,
        sum(mrr)                                as lifetime_revenue
    from {{ ref('int_account_months') }}
    group by 1
),
cur as (
    select account_id, mrr as current_mrr, seats as current_seats
    from {{ ref('int_account_months') }}
    where month = cast('{{ var("as_of_month") }}' as date)
),
plan_now as (
    select account_id, plan as current_plan
    from {{ ref('stg_subscription_events') }}
    where plan is not null
    qualify row_number() over (partition by account_id order by event_date desc, event_id desc) = 1
)
select
    a.*,
    l.first_paid_month,
    l.last_paid_month,
    l.active_months,
    l.lifetime_revenue,
    coalesce(c.current_mrr, 0)               as current_mrr,
    coalesce(c.current_seats, 0)             as current_seats,
    coalesce(p.current_plan, a.initial_plan) as current_plan,
    case
        when coalesce(c.current_mrr, 0) > 0 then 'Active'
        when l.first_paid_month is null     then 'Never paid'
        else 'Churned'
    end                                      as status,
    case
        when coalesce(c.current_mrr, 0) >= 5000 then 'Enterprise ($5k+)'
        when coalesce(c.current_mrr, 0) >= 1500 then 'Mid-market ($1.5k-5k)'
        when coalesce(c.current_mrr, 0) > 0     then 'SMB (<$1.5k)'
        else 'n/a'
    end                                      as mrr_band
from {{ ref('stg_accounts') }} a
left join life l using (account_id)
left join cur c using (account_id)
left join plan_now p using (account_id)
