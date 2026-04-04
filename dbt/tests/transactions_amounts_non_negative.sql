select *
from {{ ref('stg_transactions') }}
where amount_original < 0
   or amount_eur < 0

