select plan, tier, price_per_seat, min_seats, max_seats
from {{ source('landing', 'plans') }}
