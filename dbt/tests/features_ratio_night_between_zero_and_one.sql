select *
from {{ ref('fct_account_features') }}
where ratio_night_transactions < 0
   or ratio_night_transactions > 1

