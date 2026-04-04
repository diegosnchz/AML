-- Lookback window controlled by dbt variable alert_lookback_days (default: 90).
-- Override at runtime: dbt run --vars '{"alert_lookback_days": 180}'
with recursive chains as (
    select
        t.transaction_id as root_transaction_id,
        t.sender_account_id as root_account_id,
        t.receiver_account_id as current_account_id,
        array[t.sender_account_id, t.receiver_account_id]::text[] as account_path,
        array[t.transaction_id]::text[] as transaction_path,
        t.transaction_timestamp_utc as start_ts,
        t.transaction_timestamp_utc as last_ts,
        t.amount_eur as previous_amount,
        t.amount_eur as total_amount,
        1 as depth
    from {{ ref('stg_transactions') }} t
    where t.sender_account_id <> t.receiver_account_id
      and t.transaction_timestamp_utc >= current_timestamp - interval '{{ var("alert_lookback_days") }} days'

    union all

    select
        c.root_transaction_id,
        c.root_account_id,
        t.receiver_account_id as current_account_id,
        c.account_path || t.receiver_account_id,
        c.transaction_path || t.transaction_id,
        c.start_ts,
        t.transaction_timestamp_utc as last_ts,
        t.amount_eur as previous_amount,
        c.total_amount + t.amount_eur as total_amount,
        c.depth + 1 as depth
    from chains c
    join {{ ref('stg_transactions') }} t
        on t.sender_account_id = c.current_account_id
       and t.transaction_timestamp_utc >= c.last_ts
       and t.transaction_timestamp_utc <= c.last_ts + interval '48 hours'
       and t.amount_eur between c.previous_amount * 0.85 and c.previous_amount * 0.99
    where c.depth < 5
      and not t.receiver_account_id = any(c.account_path)
),
qualified_chains as (
    select
        root_account_id as account_id,
        account_path,
        transaction_path,
        start_ts,
        last_ts as detected_at,
        total_amount,
        depth,
        row_number() over (
            partition by root_account_id
            order by depth desc, total_amount desc, last_ts asc
        ) as rn
    from chains
    where depth >= 3
)

select
    md5(account_id || '|LAYERING|' || array_to_string(transaction_path, '|')) as alert_id,
    account_id,
    'LAYERING' as alert_type,
    case
        when depth >= 5 then 'CRITICAL'
        when depth = 4 then 'HIGH'
        else 'MEDIUM'
    end as severity,
    detected_at,
    round(total_amount, 2) as amount_involved,
    'Layering chain detected from ' || account_path[1] || ' through ' ||
    array_to_string(account_path[2:cardinality(account_path)], ' -> ') ||
    ', where each hop retained 85%-99% of the previous amount over ' || depth ||
    ' sequential transfers.' as description
from qualified_chains
where rn = 1

