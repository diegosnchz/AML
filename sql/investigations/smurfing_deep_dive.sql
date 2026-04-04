/*
Purpose:
Investigate structuring (smurfing) alerts by reconstructing the suspicious timeline around the detected 72-hour window.

Why it matters:
Repeated payments just below reporting or control thresholds are a classic AML red flag because they indicate deliberate evasion of monitoring controls.
*/

with alert_windows as (
    select
        account_id,
        detected_at,
        amount_involved,
        description,
        detected_at - interval '72 hours' as window_start
    from alerts.alert_smurfing
),
timeline as (
    select
        a.account_id,
        a.detected_at as alert_detected_at,
        a.window_start,
        t.transaction_id,
        t.transaction_timestamp_utc,
        t.receiver_account_id as beneficiary_account_id,
        t.amount_eur,
        t.currency,
        t.transaction_type,
        t.is_laundering
    from alert_windows a
    join staging.stg_transactions t
        on t.sender_account_id = a.account_id
       and t.transaction_timestamp_utc between a.window_start and a.detected_at
       and t.amount_eur < 9999
)

select
    account_id,
    alert_detected_at,
    window_start,
    transaction_id,
    transaction_timestamp_utc,
    beneficiary_account_id,
    amount_eur,
    currency,
    transaction_type,
    is_laundering,
    count(*) over (
        partition by account_id, alert_detected_at
        order by transaction_timestamp_utc
        rows between unbounded preceding and current row
    ) as cumulative_sub_threshold_txn_count,
    sum(amount_eur) over (
        partition by account_id, alert_detected_at
        order by transaction_timestamp_utc
        rows between unbounded preceding and current row
    ) as cumulative_sub_threshold_amount
from timeline
order by account_id, alert_detected_at desc, transaction_timestamp_utc

