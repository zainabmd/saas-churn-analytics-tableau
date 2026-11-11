-- One row per paying account-month: behavioural features known at month end, plus the label
-- "churned within the next N months". Rows whose label window runs past the as-of month keep a
-- null label; the latest of those is what the model scores.
{% set h = var('churn_horizon_months') %}
with feat as (
    select
        account_id,
        month,
        mrr,
        seats,
        seat_utilisation,
        features_adopted,
        logins_per_seat,
        seat_utilisation - lag(seat_utilisation, 3) over w                     as utilisation_change_3m,
        logins_per_seat / nullif(avg(logins_per_seat) over (partition by account_id order by month
                           rows between 3 preceding and 1 preceding), 0) - 1 as logins_trend_3m,
        mrr - lag(mrr, 3) over w                                               as mrr_change_3m,
        count(*) filter (where mrr > 0) over (partition by account_id order by month
                           rows between unbounded preceding and current row)  as tenure_months,
        case
            when cast(month + interval {{ h }} month as date) > cast('{{ var("as_of_month") }}' as date) then null
            when min(mrr) over (partition by account_id order by month
                     rows between 1 following and {{ h }} following) = 0 then 1
            else 0
        end                                                                    as churned_next_{{ h }}m
    from {{ ref('int_account_months') }}
    window w as (partition by account_id order by month)
),
paying as (
    select * from feat where mrr > 0
),
tickets as (
    select p.account_id, p.month,
        count(t.ticket_id)                                                    as tickets_90d,
        count(t.ticket_id) filter (where t.severity in ('High', 'Critical'))  as severe_tickets_90d,
        avg(t.csat)                                                           as csat_90d
    from paying p
    left join {{ ref('stg_support_tickets') }} t
        on t.account_id = p.account_id
       and t.opened_month >  cast(p.month - interval 3 month as date)
       and t.opened_month <= p.month
    group by 1, 2
),
nps as (
    select p.account_id, p.month, arg_max(n.score, n.responded_at) as last_nps
    from paying p
    join {{ ref('stg_nps_responses') }} n
        on n.account_id = p.account_id and n.responded_month <= p.month
    group by 1, 2
),
pay as (
    select p.account_id, p.month,
        count(i.invoice_id) filter (where i.had_payment_issue) as payment_issues_6m
    from paying p
    left join {{ ref('stg_invoices') }} i
        on i.account_id = p.account_id
       and i.invoice_month >  cast(p.month - interval 6 month as date)
       and i.invoice_month <= p.month
    group by 1, 2
)
select
    p.*,
    a.company_size,
    a.industry,
    a.region,
    a.acquisition_channel,
    a.contract_type,
    coalesce(t.tickets_90d, 0)        as tickets_90d,
    coalesce(t.severe_tickets_90d, 0) as severe_tickets_90d,
    t.csat_90d,
    n.last_nps,
    coalesce(y.payment_issues_6m, 0)  as payment_issues_6m,
    -- months until the next annual renewal (0 = renews next month boundary); monthly plans renew every month
    case when a.contract_type = 'Annual'
         then (12 - datediff('month', a.signup_month, p.month) % 12) % 12
         else 0 end                   as months_to_renewal
from paying p
join {{ ref('stg_accounts') }} a using (account_id)
left join tickets t using (account_id, month)
left join nps n using (account_id, month)
left join pay y using (account_id, month)
