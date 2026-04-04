with candidate_transactions as (
    select
        transaction_id,
        sender_account_id as account_id,
        amount_eur,
        transaction_timestamp_utc
    from {{ ref('stg_transactions') }}
    where amount_eur < 9999
),
rolling_windows as (
    select
        account_id,
        transaction_id,
        transaction_timestamp_utc,
        count(*) over (
            partition by account_id
            order by transaction_timestamp_utc
            range between interval '72 hours' preceding and current row
        ) as txn_count_72h,
        sum(amount_eur) over (
            partition by account_id
            order by transaction_timestamp_utc
            range between interval '72 hours' preceding and current row
        ) as amount_72h,
        min(transaction_timestamp_utc) over (
            partition by account_id
            order by transaction_timestamp_utc
            range between interval '72 hours' preceding and current row
        ) as window_start_72h
    from candidate_transactions
),
ranked as (
    select
        *,
        row_number() over (
            partition by account_id
            order by txn_count_72h desc, amount_72h desc, transaction_timestamp_utc asc
        ) as rn
    from rolling_windows
    where txn_count_72h >= 5
)

select
    md5(account_id || '|SMURFING|' || transaction_id) as alert_id,
    account_id,
    'SMURFING' as alert_type,
    case
        when txn_count_72h >= 15 then 'CRITICAL'
        when txn_count_72h >= 10 then 'HIGH'
        else 'MEDIUM'
    end as severity,
    transaction_timestamp_utc as detected_at,
    round(amount_72h, 2) as amount_involved,
    'Account ' || account_id || ' sent ' || txn_count_72h ||
    ' transactions below EUR 9,999 between ' || window_start_72h ||
    ' and ' || transaction_timestamp_utc ||
    ', indicating structuring activity totalling EUR ' || round(amount_72h, 2) || '.' as description
from ranked
where rn = 1

