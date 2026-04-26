-- Lookback window controlled by dbt variable alert_lookback_days (default: 90).
-- Override at runtime: dbt run --vars '{"alert_lookback_days": 180}'
with recursive paths as (
    select
        t.sender_account_id as root_account_id,
        t.receiver_account_id as current_account_id,
        array[t.sender_account_id, t.receiver_account_id]::text[] as account_path,
        array[t.transaction_id]::text[] as transaction_path,
        t.transaction_timestamp_utc as start_ts,
        t.transaction_timestamp_utc as last_ts,
        t.amount_eur as total_amount,
        1 as depth
    from {{ ref('stg_transactions') }} t
    where t.sender_account_id <> t.receiver_account_id
      and t.transaction_timestamp_utc >= current_timestamp - interval '{{ var("alert_lookback_days") }} days'

    union all

    select
        p.root_account_id,
        t.receiver_account_id as current_account_id,
        p.account_path || t.receiver_account_id,
        p.transaction_path || t.transaction_id,
        p.start_ts,
        t.transaction_timestamp_utc as last_ts,
        p.total_amount + t.amount_eur as total_amount,
        p.depth + 1 as depth
    from paths p
    join {{ ref('stg_transactions') }} t
        on t.sender_account_id = p.current_account_id
       and t.transaction_timestamp_utc >= p.last_ts
       and t.transaction_timestamp_utc <= p.start_ts + interval '7 days'
    where p.depth < 3
      and (
            (p.depth = 2 and t.receiver_account_id = p.root_account_id)
         or (p.depth < 2 and not t.receiver_account_id = any(p.account_path))
      )
),
qualified_cycles as (
    select
        root_account_id as account_id,
        account_path,
        transaction_path,
        start_ts,
        last_ts as detected_at,
        total_amount,
        row_number() over (
            partition by root_account_id
            order by total_amount desc, last_ts asc
        ) as rn
    from paths
    where depth = 3
      and current_account_id = root_account_id
      and cardinality(account_path) = 4
)

select
    md5(account_id || '|CIRCULAR|' || array_to_string(transaction_path, '|')) as alert_id,
    account_id,
    'CIRCULAR' as alert_type,
    case
        when total_amount >= 100000 then 'CRITICAL'
        when total_amount >= 50000 then 'HIGH'
        else 'MEDIUM'
    end as severity,
    detected_at,
    round(total_amount, 2) as amount_involved,
    'Circular flow detected across accounts ' || account_path[1] || ' -> ' ||
    account_path[2] || ' -> ' || account_path[3] || ' -> ' || account_path[4] ||
    ' within 7 days, recycling EUR ' || round(total_amount, 2) || '.' as description
from qualified_cycles
where rn = 1

