-- Company-level SaaS KPI table, one row per month.
with base as (
    select
        month,
        sum(mrr)                                                    as mrr,
        count(*) filter (where mrr > 0)                             as customers,
        count(*) filter (where prev_mrr > 0)                        as customers_bom,
        sum(prev_mrr)                                               as mrr_bom,
        sum(case when movement = 'new'          then mrr_delta end) as new_mrr,
        sum(case when movement = 'expansion'    then mrr_delta end) as expansion_mrr,
        sum(case when movement = 'reactivation' then mrr_delta end) as reactivation_mrr,
        -sum(case when movement = 'contraction' then mrr_delta end) as contraction_mrr,
        -sum(case when movement = 'churn'       then mrr_delta end) as churned_mrr,
        count(*) filter (where movement = 'new')                    as new_customers,
        count(*) filter (where movement = 'churn')                  as churned_customers,
        count(*) filter (where movement = 'reactivation')           as reactivated_customers
    from {{ ref('int_mrr_movements') }}
    group by 1
),
cac as (
    select signup_month as month, sum(cac_usd) as cac_spend
    from {{ ref('stg_accounts') }}
    group by 1
),
-- trailing-12-month net / gross revenue retention on customers who were paying 12 months earlier
nrr as (
    select
        cur.month,
        sum(cur.mrr)                as mrr_from_ly_customers,
        sum(least(cur.mrr, ly.mrr)) as retained_capped_mrr,
        sum(ly.mrr)                 as mrr_ly
    from {{ ref('int_account_months') }} cur
    join {{ ref('int_account_months') }} ly
        on ly.account_id = cur.account_id
       and ly.month = cast(cur.month - interval 12 month as date)
       and ly.mrr > 0
    group by 1
),
kpi as (
    select
        b.month,
        b.mrr,
        b.mrr * 12                      as arr,
        b.customers,
        b.customers_bom,
        b.mrr_bom,
        coalesce(b.new_mrr, 0)          as new_mrr,
        coalesce(b.expansion_mrr, 0)    as expansion_mrr,
        coalesce(b.reactivation_mrr, 0) as reactivation_mrr,
        coalesce(b.contraction_mrr, 0)  as contraction_mrr,
        coalesce(b.churned_mrr, 0)      as churned_mrr,
        b.new_customers,
        b.churned_customers,
        b.reactivated_customers,
        c.cac_spend,
        n.mrr_from_ly_customers,
        n.retained_capped_mrr,
        n.mrr_ly
    from base b
    left join cac c using (month)
    left join nrr n using (month)
)
select
    month,
    mrr,
    arr,
    customers,
    new_mrr,
    expansion_mrr,
    reactivation_mrr,
    contraction_mrr,
    churned_mrr,
    new_mrr + expansion_mrr + reactivation_mrr - contraction_mrr - churned_mrr as net_new_mrr,
    new_customers,
    churned_customers,
    reactivated_customers,
    churned_customers / nullif(customers_bom, 0)                     as logo_churn_rate,
    (churned_mrr + contraction_mrr) / nullif(mrr_bom, 0)             as gross_mrr_churn_rate,
    expansion_mrr / nullif(mrr_bom, 0)                               as expansion_rate,
    mrr / nullif(customers, 0)                                       as arpa,
    (new_mrr + expansion_mrr + reactivation_mrr)
        / nullif(contraction_mrr + churned_mrr, 0)                   as quick_ratio,
    mrr_from_ly_customers / nullif(mrr_ly, 0)                        as nrr_ttm,
    retained_capped_mrr / nullif(mrr_ly, 0)                          as grr_ttm,
    cac_spend,
    cac_spend / nullif(new_customers, 0)                             as cac_per_customer,
    -- LTV = ARPA x gross margin / monthly logo churn (trailing 3-month average to damp noise)
    (mrr / nullif(customers, 0)) * {{ var('gross_margin') }}
        / nullif(avg(churned_customers / nullif(customers_bom, 0))
                 over (order by month rows between 2 preceding and current row), 0) as ltv
from kpi
order by month
