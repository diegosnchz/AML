with deduplicated as (
    select distinct on (transaction_id)
        transaction_id,
        transaction_timestamp_utc,
        sender_account_id,
        receiver_account_id,
        amount_original,
        amount_eur,
        upper(currency) as currency,
        upper(transaction_type) as transaction_type,
        is_laundering::integer as is_laundering,
        ingestion_timestamp
    from {{ source('raw', 'transactions') }}
    where transaction_id is not null
      and sender_account_id is not null
      and receiver_account_id is not null
      and transaction_timestamp_utc is not null
      and amount_eur is not null
    order by transaction_id, ingestion_timestamp desc
)

select
    transaction_id,
    transaction_timestamp_utc,
    sender_account_id,
    receiver_account_id,
    amount_original,
    amount_eur,
    currency,
    transaction_type,
    is_laundering,
    ingestion_timestamp
from deduplicated

