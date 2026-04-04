/*
Purpose:
Expose accounts that disperse funds across many beneficiaries and show where the money was distributed within the alert window.

Why it matters:
Fan-out behavior is common in mule-account networks, payout hubs, and layering stages where illicit proceeds are quickly fragmented after receipt.
*/

with fan_out_windows as (
    select
        account_id,
        detected_at,
        amount_involved,
        detected_at - interval '24 hours' as window_start
    from alerts.alert_fan_out
),
distribution as (
    select
        f.account_id,
        f.window_start,
        f.detected_at,
        t.receiver_account_id as beneficiary_account_id,
        acc.country as beneficiary_country,
        count(*) as txn_count,
        round(sum(t.amount_eur), 2) as total_amount,
        round(avg(t.amount_eur), 2) as avg_amount
    from fan_out_windows f
    join staging.stg_transactions t
        on t.sender_account_id = f.account_id
       and t.transaction_timestamp_utc between f.window_start and f.detected_at
    left join staging.stg_accounts acc
        on t.receiver_account_id = acc.account_id
    group by 1, 2, 3, 4, 5
)

select
    account_id,
    window_start,
    detected_at,
    beneficiary_account_id,
    beneficiary_country,
    txn_count,
    total_amount,
    avg_amount,
    dense_rank() over (
        partition by account_id, detected_at
        order by total_amount desc
    ) as beneficiary_rank_by_amount
from distribution
order by account_id, detected_at desc, total_amount desc

