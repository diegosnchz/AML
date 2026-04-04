/*
Purpose:
Assemble a full escalation pack for SAR review candidates, combining account master data, alert activity, ML score, graph metrics, and transaction statistics.

Why it matters:
Analysts need a single, investigation-ready view to document suspicion, assess materiality, and decide whether a case should move to formal SAR drafting.
*/

with transaction_stats as (
    select
        account_id,
        count(*) as n_transactions,
        round(sum(amount_eur), 2) as total_transaction_amount,
        round(max(amount_eur), 2) as max_transaction_amount,
        max(transaction_timestamp_utc) as last_transaction_at
    from (
        select sender_account_id as account_id, amount_eur, transaction_timestamp_utc
        from staging.stg_transactions
        union all
        select receiver_account_id as account_id, amount_eur, transaction_timestamp_utc
        from staging.stg_transactions
    ) t
    group by account_id
),
alert_detail as (
    select
        account_id,
        string_agg(alert_type || ' [' || severity || ']', ', ' order by detected_at desc) as alert_timeline
    from alerts.fct_alerts
    group by account_id
)

select
    s.account_id,
    acc.account_name,
    acc.country,
    acc.account_type,
    s.alert_count,
    s.critical_alert_count,
    s.max_severity,
    s.alert_types,
    s.sar_rationale,
    s.first_alert_at,
    s.latest_alert_at,
    s.total_amount_involved,
    r.risk_score,
    r.risk_tier,
    r.top_3_features,
    g.pagerank_score,
    g.community_id,
    ts.n_transactions,
    ts.total_transaction_amount,
    ts.max_transaction_amount,
    ts.last_transaction_at,
    ad.alert_timeline
from alerts.fct_sar_candidates s
left join staging.stg_accounts acc
    on s.account_id = acc.account_id
left join ml.risk_scores r
    on s.account_id = r.account_id
left join ml.graph_account_metrics g
    on s.account_id = g.account_id
left join transaction_stats ts
    on s.account_id = ts.account_id
left join alert_detail ad
    on s.account_id = ad.account_id
order by s.critical_alert_count desc, r.risk_score desc nulls last, g.pagerank_score desc nulls last

