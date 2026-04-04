with anchored_windows as (
    select
        a.receiver_account_id as account_id,
        a.transaction_id as anchor_transaction_id,
        a.transaction_timestamp_utc as window_start,
        max(b.transaction_timestamp_utc) as window_end,
        count(*) as txn_count_24h,
        count(distinct b.sender_account_id) as distinct_senders_24h,
        sum(b.amount_eur) as amount_24h
    from {{ ref('stg_transactions') }} a
    join {{ ref('stg_transactions') }} b
        on a.receiver_account_id = b.receiver_account_id
       and b.transaction_timestamp_utc between a.transaction_timestamp_utc
           and a.transaction_timestamp_utc + interval '24 hours'
    group by 1, 2, 3
    having count(distinct b.sender_account_id) >= 10
),
ranked as (
    select
        *,
        row_number() over (
            partition by account_id
            order by distinct_senders_24h desc, amount_24h desc, window_start asc
        ) as rn
    from anchored_windows
)

select
    md5(account_id || '|FAN_IN|' || anchor_transaction_id) as alert_id,
    account_id,
    'FAN_IN' as alert_type,
    case
        when distinct_senders_24h >= 20 then 'CRITICAL'
        when distinct_senders_24h >= 15 then 'HIGH'
        else 'MEDIUM'
    end as severity,
    window_end as detected_at,
    round(amount_24h, 2) as amount_involved,
    'Account ' || account_id || ' received funds from ' || distinct_senders_24h ||
    ' unique originators within 24 hours between ' || window_start || ' and ' ||
    window_end || ', suggesting consolidation activity or a mule collection node.' as description
from ranked
where rn = 1

