/*
Purpose:
Reconstruct complete circular transaction chains of the form A -> B -> C -> A within seven days.

Why it matters:
Circular movement is a strong layering indicator because funds are routed through multiple parties and returned to the origin to obscure provenance and beneficial ownership.
*/

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
    from staging.stg_transactions t
    where t.sender_account_id <> t.receiver_account_id

    union all

    select
        p.root_account_id,
        t.receiver_account_id,
        p.account_path || t.receiver_account_id,
        p.transaction_path || t.transaction_id,
        p.start_ts,
        t.transaction_timestamp_utc,
        p.total_amount + t.amount_eur,
        p.depth + 1
    from paths p
    join staging.stg_transactions t
        on t.sender_account_id = p.current_account_id
       and t.transaction_timestamp_utc >= p.last_ts
       and t.transaction_timestamp_utc <= p.start_ts + interval '7 days'
    where p.depth < 3
      and (
            (p.depth = 2 and t.receiver_account_id = p.root_account_id)
         or (p.depth < 2 and not t.receiver_account_id = any(p.account_path))
      )
)

select
    root_account_id,
    account_path[1] as account_a,
    account_path[2] as account_b,
    account_path[3] as account_c,
    transaction_path[1] as tx_ab,
    transaction_path[2] as tx_bc,
    transaction_path[3] as tx_ca,
    start_ts as first_leg_timestamp,
    last_ts as final_leg_timestamp,
    round(total_amount, 2) as circular_amount
from paths
where depth = 3
  and current_account_id = root_account_id
  and cardinality(account_path) = 4
order by circular_amount desc, final_leg_timestamp desc

