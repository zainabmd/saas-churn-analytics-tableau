-- Warehouse MRR must agree with the billing system. Subscriptions starting on the 1st bill that
-- month; mid-month plan changes and cancellations bill from the next cycle. So the MRR billed in the
-- as-of month is the MRR after each account's last event dated on or before the 1st of that month,
-- and it must equal dim_accounts.current_mrr.
with last_evt as (
    select account_id, mrr_after
    from {{ ref('stg_subscription_events') }}
    where event_date <= cast('{{ var("as_of_month") }}' as date)
    qualify row_number() over (partition by account_id order by event_date desc, event_id desc) = 1
)
select e.account_id, e.mrr_after, d.current_mrr
from last_evt e
join {{ ref('dim_accounts') }} d using (account_id)
where abs(e.mrr_after - d.current_mrr) > 0.01
