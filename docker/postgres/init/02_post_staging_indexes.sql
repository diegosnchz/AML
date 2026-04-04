-- Post-staging indexes for AMLGuardian
--
-- These indexes target tables created by dbt staging models (staging.stg_transactions,
-- staging.stg_accounts). They do NOT exist at container init time and CANNOT be
-- applied by 01_init.sql. Run this file manually after the first dbt staging run:
--
--   docker exec -i amlguardian-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB \
--     < docker/postgres/init/02_post_staging_indexes.sql
--
-- Alternatively, attach these as dbt post-hooks on the staging models if the
-- project grows to warrant it. All statements are idempotent (IF NOT EXISTS).

-- Support fct_account_features GROUP BY account_id and velocity_7d window filter
CREATE INDEX IF NOT EXISTS idx_stg_transactions_sender_ts
    ON staging.stg_transactions (sender_account_id, transaction_timestamp_utc);

CREATE INDEX IF NOT EXISTS idx_stg_transactions_receiver_ts
    ON staging.stg_transactions (receiver_account_id, transaction_timestamp_utc);

-- Support the alert_lookback_days base-case filter on both recursive CTE models
CREATE INDEX IF NOT EXISTS idx_stg_transactions_ts
    ON staging.stg_transactions (transaction_timestamp_utc);

-- Support left joins from fct_account_features and alert models into stg_accounts
CREATE INDEX IF NOT EXISTS idx_stg_accounts_id
    ON staging.stg_accounts (account_id);
