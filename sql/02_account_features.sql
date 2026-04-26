-- Account-level features for analyst review and dashboarding.

WITH account_transactions AS (
    SELECT
        sender_account_id AS account_id,
        receiver_account_id AS counterparty_account_id,
        amount_eur,
        'OUTBOUND' AS direction
    FROM transactions

    UNION ALL

    SELECT
        receiver_account_id AS account_id,
        sender_account_id AS counterparty_account_id,
        amount_eur,
        'INBOUND' AS direction
    FROM transactions
)
SELECT
    a.account_id,
    a.country,
    COUNT(at.account_id) AS transaction_count,
    ROUND(SUM(CASE WHEN at.direction = 'INBOUND' THEN at.amount_eur ELSE 0 END), 2) AS total_inbound_amount,
    ROUND(SUM(CASE WHEN at.direction = 'OUTBOUND' THEN at.amount_eur ELSE 0 END), 2) AS total_outbound_amount,
    COUNT(DISTINCT at.counterparty_account_id) AS unique_counterparties,
    ROUND(AVG(at.amount_eur), 2) AS average_transaction_amount
FROM accounts a
LEFT JOIN account_transactions at
    ON a.account_id = at.account_id
GROUP BY a.account_id, a.country;
