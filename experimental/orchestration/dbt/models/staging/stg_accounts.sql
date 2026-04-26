with deduplicated as (
    select distinct on (account_id)
        account_id,
        trim(account_name) as account_name,
        upper(trim(country)) as country,
        upper(trim(account_type)) as account_type,
        ingestion_timestamp
    from {{ source('raw', 'accounts') }}
    where account_id is not null
    order by account_id, ingestion_timestamp desc
)

select
    account_id,
    account_name,
    country,
    account_type,
    ingestion_timestamp
from deduplicated

