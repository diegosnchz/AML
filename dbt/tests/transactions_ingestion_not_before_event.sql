select *
from {{ ref('stg_transactions') }}
where ingestion_timestamp < transaction_timestamp_utc

