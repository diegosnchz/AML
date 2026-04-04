select *
from {{ ref('fct_alerts') }}
where amount_involved <= 0

