-- Logo and revenue retention by first-payment cohort x months since start, split by segment.
with firsts as (
    select account_id, min(month) as cohort_month
    from {{ ref('int_account_months') }}
    where is_active
    group by 1
),
base as (
    select
        f.cohort_month,
        datediff('month', f.cohort_month, m.month) as months_since_start,
        a.company_size,
        a.contract_type,
        m.account_id,
        m.mrr
    from {{ ref('int_account_months') }} m
    join firsts f using (account_id)
    join {{ ref('stg_accounts') }} a using (account_id)
    where m.month >= f.cohort_month
),
start as (
    select account_id, mrr as start_mrr from base where months_since_start = 0
)
select
    b.cohort_month,
    b.months_since_start,
    b.company_size,
    b.contract_type,
    count(*)                          as cohort_customers,
    count(*) filter (where b.mrr > 0) as active_customers,
    sum(s.start_mrr)                  as cohort_start_mrr,
    sum(b.mrr)                        as mrr
from base b
join start s using (account_id)
group by all
