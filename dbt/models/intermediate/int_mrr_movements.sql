-- Classify every account-month into one MRR movement. new + expansion + reactivation
-- - contraction - churn equals the month-over-month change in total MRR (tested in tests/).
select
    account_id,
    month,
    prev_mrr,
    mrr,
    mrr - prev_mrr as mrr_delta,
    case
        when prev_mrr = 0 and mrr > 0 and not was_ever_active then 'new'
        when prev_mrr = 0 and mrr > 0                          then 'reactivation'
        when prev_mrr > 0 and mrr = 0                          then 'churn'
        when mrr > prev_mrr                                    then 'expansion'
        when mrr < prev_mrr                                    then 'contraction'
        when mrr > 0                                           then 'retained'
        else 'inactive'
    end as movement
from {{ ref('int_account_months') }}
