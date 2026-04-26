select *
from {{ ref('fct_sar_candidates') }}
where alert_count < 3
  and critical_alert_count = 0

