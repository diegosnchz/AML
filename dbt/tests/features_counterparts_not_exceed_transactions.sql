select *
from {{ ref('fct_account_features') }}
where n_unique_counterparts > n_transactions

