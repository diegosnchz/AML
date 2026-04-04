/*
Purpose:
Prioritize accounts that combine multiple alert typologies with a high machine-learning risk score.

Why it matters:
Accounts that trigger diverse rule-based indicators and also score highly in the behavioral model warrant accelerated review because they exhibit both known typologies and anomalous aggregate behavior.
*/

with alert_summary as (
    select
        account_id,
        count(*) as alert_count,
        count(distinct alert_type) as alert_type_count,
        string_agg(distinct alert_type, ', ' order by alert_type) as alert_types,
        max(case severity
            when 'CRITICAL' then 4
            when 'HIGH' then 3
            when 'MEDIUM' then 2
            else 1
        end) as max_severity_rank,
        round(sum(amount_involved), 2) as total_alert_amount
    from alerts.fct_alerts
    group by account_id
)

select
    a.account_id,
    acc.account_name,
    acc.country,
    acc.account_type,
    a.alert_count,
    a.alert_type_count,
    a.alert_types,
    case a.max_severity_rank
        when 4 then 'CRITICAL'
        when 3 then 'HIGH'
        when 2 then 'MEDIUM'
        else 'LOW'
    end as max_alert_severity,
    a.total_alert_amount,
    r.risk_score,
    r.risk_tier,
    r.top_3_features
from alert_summary a
join ml.risk_scores r
    on a.account_id = r.account_id
left join staging.stg_accounts acc
    on a.account_id = acc.account_id
where a.alert_type_count >= 2
  and r.risk_score >= 70
order by r.risk_score desc, a.alert_count desc, a.total_alert_amount desc

