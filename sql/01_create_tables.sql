-- Simple SQLite-friendly schema for practicing the project with SQL.

DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS transactions;

CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    account_name TEXT,
    country TEXT,
    account_type TEXT
);

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    transaction_timestamp TEXT,
    transaction_date TEXT,
    sender_account_id TEXT,
    receiver_account_id TEXT,
    amount_original REAL,
    amount_eur REAL,
    currency TEXT,
    transaction_type TEXT,
    is_laundering INTEGER
);
