-- MRR bridge by month x movement x segment (Tableau waterfall / stacked bars).
select
    m.month,
    m.movement,
    a.company_size,
    a.region,
    a.industry,
    a.acquisition_channel,
    a.contract_type,
    count(*)         as accounts,
    sum(m.mrr_delta) as mrr_delta
from {{ ref('int_mrr_movements') }} m
join {{ ref('stg_accounts') }} a using (account_id)
where m.movement not in ('retained', 'inactive')
group by all
