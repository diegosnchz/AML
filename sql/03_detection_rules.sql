-- Simplified detection rules for practice.
-- These queries are examples; the Python scripts generate the sample output CSV.

-- 1. Smurfing / structuring: several lower-value outgoing transfers in 72 hours.
SELECT
    t1.sender_account_id AS account_id,
    'SMURFING' AS rule_name,
    COUNT(*) AS transaction_count_72h,
    ROUND(SUM(t2.amount_eur), 2) AS amount_72h_eur,
    MIN(t2.transaction_timestamp) AS window_start,
    MAX(t2.transaction_timestamp) AS window_end
FROM transactions t1
JOIN transactions t2
    ON t1.sender_account_id = t2.sender_account_id
   AND t2.transaction_timestamp BETWEEN t1.transaction_timestamp
       AND datetime(t1.transaction_timestamp, '+72 hours')
WHERE t2.amount_eur < 9999
GROUP BY t1.sender_account_id, t1.transaction_timestamp
HAVING COUNT(*) >= 5;

-- 2. Fan-in: one account receives funds from several unique originators in 24 hours.
SELECT
    t1.receiver_account_id AS account_id,
    'FAN_IN' AS rule_name,
    COUNT(DISTINCT t2.sender_account_id) AS unique_originators_24h,
    ROUND(SUM(t2.amount_eur), 2) AS amount_24h_eur,
    MIN(t2.transaction_timestamp) AS window_start,
    MAX(t2.transaction_timestamp) AS window_end
FROM transactions t1
JOIN transactions t2
    ON t1.receiver_account_id = t2.receiver_account_id
   AND t2.transaction_timestamp BETWEEN t1.transaction_timestamp
       AND datetime(t1.transaction_timestamp, '+24 hours')
GROUP BY t1.receiver_account_id, t1.transaction_timestamp
HAVING COUNT(DISTINCT t2.sender_account_id) >= 5;

-- 3. Fan-out: one account sends funds to several unique beneficiaries in 24 hours.
SELECT
    t1.sender_account_id AS account_id,
    'FAN_OUT' AS rule_name,
    COUNT(DISTINCT t2.receiver_account_id) AS unique_beneficiaries_24h,
    ROUND(SUM(t2.amount_eur), 2) AS amount_24h_eur,
    MIN(t2.transaction_timestamp) AS window_start,
    MAX(t2.transaction_timestamp) AS window_end
FROM transactions t1
JOIN transactions t2
    ON t1.sender_account_id = t2.sender_account_id
   AND t2.transaction_timestamp BETWEEN t1.transaction_timestamp
       AND datetime(t1.transaction_timestamp, '+24 hours')
GROUP BY t1.sender_account_id, t1.transaction_timestamp
HAVING COUNT(DISTINCT t2.receiver_account_id) >= 5;

-- 4. High-risk geography: transaction touches a training watchlist country.
SELECT
    t.transaction_id,
    t.sender_account_id,
    t.receiver_account_id,
    t.amount_eur,
    s.country AS sender_country,
    r.country AS receiver_country
FROM transactions t
LEFT JOIN accounts s
    ON t.sender_account_id = s.account_id
LEFT JOIN accounts r
    ON t.receiver_account_id = r.account_id
WHERE s.country IN ('IRAN', 'MYANMAR', 'DPRK', 'SYRIA', 'YEMEN')
   OR r.country IN ('IRAN', 'MYANMAR', 'DPRK', 'SYRIA', 'YEMEN');

-- Optional advanced practice: circular flow A -> B -> C -> A.
-- This is included as a learning exercise, not as a required rule in the main pipeline.
SELECT
    t1.sender_account_id AS account_a,
    t1.receiver_account_id AS account_b,
    t2.receiver_account_id AS account_c,
    t3.receiver_account_id AS returned_to_account,
    t1.transaction_timestamp AS start_time,
    t3.transaction_timestamp AS end_time,
    ROUND(t1.amount_eur + t2.amount_eur + t3.amount_eur, 2) AS total_loop_amount
FROM transactions t1
JOIN transactions t2
    ON t1.receiver_account_id = t2.sender_account_id
   AND t2.transaction_timestamp > t1.transaction_timestamp
JOIN transactions t3
    ON t2.receiver_account_id = t3.sender_account_id
   AND t3.receiver_account_id = t1.sender_account_id
   AND t3.transaction_timestamp > t2.transaction_timestamp
WHERE t3.transaction_timestamp <= datetime(t1.transaction_timestamp, '+7 days');
