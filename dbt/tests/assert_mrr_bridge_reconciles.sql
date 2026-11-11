-- Every month, opening MRR + net new MRR must equal closing MRR (to the cent).
with m as (
    select month, mrr, net_new_mrr, lag(mrr) over (order by month) as prev_mrr
    from {{ ref('fct_saas_metrics_monthly') }}
)
select *
from m
where abs(coalesce(prev_mrr, 0) + net_new_mrr - mrr) > 0.01
