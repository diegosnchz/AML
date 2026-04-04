with account_transactions as (
    select
        sender_account_id as account_id,
        receiver_account_id as counterpart_account_id,
        amount_eur,
        transaction_timestamp_utc,
        is_laundering,
        'SENT' as transaction_direction
    from {{ ref('stg_transactions') }}

    union all

    select
        receiver_account_id as account_id,
        sender_account_id as counterpart_account_id,
        amount_eur,
        transaction_timestamp_utc,
        is_laundering,
        'RECEIVED' as transaction_direction
    from {{ ref('stg_transactions') }}
),
dataset_max_timestamp as (
    select max(transaction_timestamp_utc) as max_transaction_timestamp
    from {{ ref('stg_transactions') }}
),
aggregated as (
    select
        t.account_id,
        round(sum(case when t.transaction_direction = 'SENT' then t.amount_eur else 0 end), 2) as total_sent,
        round(sum(case when t.transaction_direction = 'RECEIVED' then t.amount_eur else 0 end), 2) as total_received,
        count(*) as n_transactions,
        round(avg(case when t.transaction_direction = 'SENT' then t.amount_eur end), 2) as avg_amount_sent,
        round(coalesce(stddev_samp(case when t.transaction_direction = 'SENT' then t.amount_eur end), 0), 2) as stddev_amount_sent,
        count(distinct t.counterpart_account_id) as n_unique_counterparts,
        count(distinct counterpart.country) as n_countries_transacted,
        round(
            count(*) filter (
                where extract(hour from t.transaction_timestamp_utc) between 0 and 5
            )::numeric / nullif(count(*), 0),
            4
        ) as ratio_night_transactions,
        round(max(t.amount_eur), 2) as max_single_transaction,
        round(
            sum(
                case
                    when t.transaction_direction = 'SENT'
                     and t.transaction_timestamp_utc >= d.max_transaction_timestamp - interval '7 days'
                    then t.amount_eur
                    else 0
                end
            ),
            2
        ) as velocity_7d,
        max(t.is_laundering) as is_laundering_any
    from account_transactions t
    left join {{ ref('stg_accounts') }} counterpart
        on t.counterpart_account_id = counterpart.account_id
    cross join dataset_max_timestamp d
    group by t.account_id
)

select
    a.account_id,
    coalesce(f.total_sent, 0) as total_sent,
    coalesce(f.total_received, 0) as total_received,
    coalesce(f.n_transactions, 0) as n_transactions,
    coalesce(f.avg_amount_sent, 0) as avg_amount_sent,
    coalesce(f.stddev_amount_sent, 0) as stddev_amount_sent,
    coalesce(f.n_unique_counterparts, 0) as n_unique_counterparts,
    coalesce(f.n_countries_transacted, 0) as n_countries_transacted,
    coalesce(f.ratio_night_transactions, 0) as ratio_night_transactions,
    coalesce(f.max_single_transaction, 0) as max_single_transaction,
    coalesce(f.velocity_7d, 0) as velocity_7d,
    coalesce(f.is_laundering_any, 0) as is_laundering_any
from {{ ref('stg_accounts') }} a
left join aggregated f
    on a.account_id = f.account_id

