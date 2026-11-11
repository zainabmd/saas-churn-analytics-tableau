select
    invoice_id,
    account_id,
    cast(invoice_month as date) as invoice_month,
    cast(amount_usd as double)  as amount_usd,
    status,
    status = 'failed'           as is_failed,
    status in ('failed', 'recovered') as had_payment_issue
from {{ source('landing', 'invoices') }}
