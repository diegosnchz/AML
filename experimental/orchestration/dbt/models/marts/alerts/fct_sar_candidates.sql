with alert_summary as (
    select
        account_id,
        count(*) as alert_count,
        count(*) filter (where severity = 'CRITICAL') as critical_alert_count,
        min(detected_at) as first_alert_at,
        max(detected_at) as latest_alert_at,
        round(sum(amount_involved), 2) as total_amount_involved,
        case
            when max(case severity
                when 'CRITICAL' then 4
                when 'HIGH' then 3
                when 'MEDIUM' then 2
                else 1
            end) = 4 then 'CRITICAL'
            when max(case severity
                when 'CRITICAL' then 4
                when 'HIGH' then 3
                when 'MEDIUM' then 2
                else 1
            end) = 3 then 'HIGH'
            when max(case severity
                when 'CRITICAL' then 4
                when 'HIGH' then 3
                when 'MEDIUM' then 2
                else 1
            end) = 2 then 'MEDIUM'
            else 'LOW'
        end as max_severity,
        string_agg(distinct alert_type, ', ' order by alert_type) as alert_types
    from {{ ref('fct_alerts') }}
    group by account_id
)

select
    account_id,
    alert_count,
    critical_alert_count,
    max_severity,
    alert_types,
    first_alert_at,
    latest_alert_at,
    total_amount_involved,
    case
        when critical_alert_count > 0 then 'CRITICAL severity alert present'
        else 'Three or more alert typologies accumulated'
    end as sar_rationale
from alert_summary
where alert_count >= 3
   or critical_alert_count > 0

