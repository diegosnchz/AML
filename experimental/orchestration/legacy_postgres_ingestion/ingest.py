from __future__ import annotations

import re
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import psycopg2

from common import configure_logging, env


LOGGER = configure_logging("amlguardian.ingest")
CHUNK_SIZE = 100_000
FX_RATES = {
    "EUR": 1.00,
    "USD": 0.92,
    "GBP": 1.17,
    "CHF": 1.04,
}


def postgres_connection():
    return psycopg2.connect(
        host=env("POSTGRES_HOST", "localhost"),
        port=env("POSTGRES_PORT", "5432"),
        dbname=env("POSTGRES_DB", required=True),
        user=env("POSTGRES_USER", required=True),
        password=env("POSTGRES_PASSWORD", required=True),
    )


def normalize_headers(columns: list[str]) -> list[str]:
    normalized = []
    for column in columns:
        column = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", column)
        column = re.sub(r"[^a-zA-Z0-9]+", "_", column).strip("_")
        normalized.append(column.lower())
    return normalized


def normalize_currency(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "EUR"
    cleaned = str(value).strip().upper()
    return cleaned or "EUR"


def clean_transactions(chunk: pd.DataFrame, ingested_at: datetime) -> pd.DataFrame:
    chunk = chunk.copy()
    chunk.columns = normalize_headers(chunk.columns.tolist())

    rename_map = {
        "transaction_id": "transaction_id",
        "timestamp": "transaction_timestamp_utc",
        "sender_account_id": "sender_account_id",
        "receiver_account_id": "receiver_account_id",
        "amount": "amount_original",
        "currency": "currency",
        "transaction_type": "transaction_type",
        "is_laundering": "is_laundering",
    }
    chunk = chunk.rename(columns=rename_map)

    required_columns = [
        "transaction_id",
        "transaction_timestamp_utc",
        "sender_account_id",
        "receiver_account_id",
        "amount_original",
        "currency",
        "transaction_type",
        "is_laundering",
    ]
    for column in required_columns:
        if column not in chunk.columns:
            raise ValueError(f"Missing expected transaction column: {column}")

    chunk["transaction_id"] = chunk["transaction_id"].astype(str).str.strip()
    chunk["sender_account_id"] = chunk["sender_account_id"].astype(str).str.strip()
    chunk["receiver_account_id"] = chunk["receiver_account_id"].astype(str).str.strip()
    chunk["currency"] = chunk["currency"].apply(normalize_currency)
    chunk["transaction_type"] = (
        chunk["transaction_type"].fillna("UNKNOWN").astype(str).str.strip().str.upper()
    )

    chunk["amount_original"] = pd.to_numeric(chunk["amount_original"], errors="coerce")
    chunk["amount_eur"] = (
        chunk["amount_original"] * chunk["currency"].map(FX_RATES).fillna(1.0)
    ).round(2)
    chunk["transaction_timestamp_utc"] = pd.to_datetime(
        chunk["transaction_timestamp_utc"], errors="coerce", utc=True
    )
    chunk["is_laundering"] = (
        pd.to_numeric(chunk["is_laundering"], errors="coerce")
        .fillna(0)
        .clip(lower=0, upper=1)
        .astype(int)
    )
    chunk["ingestion_timestamp"] = ingested_at

    before = len(chunk)
    chunk = chunk.dropna(
        subset=[
            "transaction_timestamp_utc",
            "amount_original",
            "amount_eur",
        ]
    )
    chunk = chunk[
        (chunk["transaction_id"] != "")
        & (chunk["sender_account_id"] != "")
        & (chunk["receiver_account_id"] != "")
    ]
    chunk = chunk.drop_duplicates(subset=["transaction_id"])
    dropped = before - len(chunk)
    if dropped:
        LOGGER.info("Dropped %s invalid or duplicate transaction rows in current chunk", dropped)

    return chunk[
        [
            "transaction_id",
            "transaction_timestamp_utc",
            "sender_account_id",
            "receiver_account_id",
            "amount_original",
            "amount_eur",
            "currency",
            "transaction_type",
            "is_laundering",
            "ingestion_timestamp",
        ]
    ]


def clean_accounts(accounts: pd.DataFrame, ingested_at: datetime) -> pd.DataFrame:
    accounts = accounts.copy()
    accounts.columns = normalize_headers(accounts.columns.tolist())
    rename_map = {
        "account_id": "account_id",
        "name": "account_name",
        "country": "country",
        "account_type": "account_type",
    }
    accounts = accounts.rename(columns=rename_map)

    required_columns = ["account_id", "account_name", "country", "account_type"]
    for column in required_columns:
        if column not in accounts.columns:
            raise ValueError(f"Missing expected account column: {column}")

    accounts["account_id"] = accounts["account_id"].astype(str).str.strip()
    accounts["account_name"] = accounts["account_name"].fillna("UNKNOWN").astype(str).str.strip()
    accounts["country"] = accounts["country"].fillna("UNKNOWN").astype(str).str.strip().str.upper()
    accounts["account_type"] = (
        accounts["account_type"].fillna("UNKNOWN").astype(str).str.strip().str.upper()
    )
    accounts["ingestion_timestamp"] = ingested_at

    before = len(accounts)
    accounts = accounts[accounts["account_id"] != ""].drop_duplicates(subset=["account_id"])
    dropped = before - len(accounts)
    if dropped:
        LOGGER.info("Dropped %s invalid or duplicate account rows", dropped)

    return accounts[required_columns + ["ingestion_timestamp"]]


def copy_dataframe(cursor, dataframe: pd.DataFrame, table_name: str, columns: list[str]) -> None:
    buffer = StringIO()
    dataframe.to_csv(buffer, index=False, header=False, na_rep="\\N")
    buffer.seek(0)
    quoted_columns = ", ".join(columns)
    cursor.copy_expert(
        f"COPY {table_name} ({quoted_columns}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')",
        buffer,
    )


def prepare_raw_tables(connection) -> None:
    ddl = """
    CREATE SCHEMA IF NOT EXISTS raw;

    DROP TABLE IF EXISTS raw.transactions;
    CREATE TABLE raw.transactions (
        transaction_id TEXT,
        transaction_timestamp_utc TIMESTAMPTZ,
        sender_account_id TEXT,
        receiver_account_id TEXT,
        amount_original NUMERIC(18, 2),
        amount_eur NUMERIC(18, 2),
        currency TEXT,
        transaction_type TEXT,
        is_laundering INTEGER,
        ingestion_timestamp TIMESTAMPTZ
    );

    DROP TABLE IF EXISTS raw.accounts;
    CREATE TABLE raw.accounts (
        account_id TEXT,
        account_name TEXT,
        country TEXT,
        account_type TEXT,
        ingestion_timestamp TIMESTAMPTZ
    );
    """
    with connection.cursor() as cursor:
        cursor.execute(ddl)
    connection.commit()


def post_load_housekeeping(connection) -> None:
    statements = [
        """
        DELETE FROM raw.transactions a
        USING raw.transactions b
        WHERE a.ctid < b.ctid
          AND a.transaction_id = b.transaction_id;
        """,
        """
        DELETE FROM raw.accounts a
        USING raw.accounts b
        WHERE a.ctid < b.ctid
          AND a.account_id = b.account_id;
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_raw_transactions_id ON raw.transactions (transaction_id);
        CREATE INDEX IF NOT EXISTS idx_raw_transactions_sender_ts
            ON raw.transactions (sender_account_id, transaction_timestamp_utc);
        CREATE INDEX IF NOT EXISTS idx_raw_transactions_receiver_ts
            ON raw.transactions (receiver_account_id, transaction_timestamp_utc);
        CREATE INDEX IF NOT EXISTS idx_raw_accounts_id ON raw.accounts (account_id);
        """,
    ]
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
    connection.commit()


def ingest_accounts(connection, accounts_path: Path, ingested_at: datetime) -> int:
    LOGGER.info("Reading accounts from %s", accounts_path)
    accounts = pd.read_csv(accounts_path)
    cleaned = clean_accounts(accounts, ingested_at)
    with connection.cursor() as cursor:
        copy_dataframe(
            cursor,
            cleaned,
            "raw.accounts",
            ["account_id", "account_name", "country", "account_type", "ingestion_timestamp"],
        )
    connection.commit()
    LOGGER.info("Loaded %s account rows into raw.accounts", len(cleaned))
    return len(cleaned)


def ingest_transactions(connection, transactions_path: Path, ingested_at: datetime) -> int:
    LOGGER.info("Reading transactions from %s in chunks of %s", transactions_path, CHUNK_SIZE)
    total_rows = 0
    for chunk_number, chunk in enumerate(pd.read_csv(transactions_path, chunksize=CHUNK_SIZE), start=1):
        cleaned = clean_transactions(chunk, ingested_at)
        with connection.cursor() as cursor:
            copy_dataframe(
                cursor,
                cleaned,
                "raw.transactions",
                [
                    "transaction_id",
                    "transaction_timestamp_utc",
                    "sender_account_id",
                    "receiver_account_id",
                    "amount_original",
                    "amount_eur",
                    "currency",
                    "transaction_type",
                    "is_laundering",
                    "ingestion_timestamp",
                ],
            )
        connection.commit()
        total_rows += len(cleaned)
        LOGGER.info(
            "Processed chunk %s | cumulative transactions loaded: %s",
            chunk_number,
            total_rows,
        )
    return total_rows


def main() -> None:
    transactions_path = Path(env("TRANSACTIONS_CSV", required=True))
    accounts_path = Path(env("ACCOUNTS_CSV", required=True))
    ingested_at = datetime.now(tz=UTC)

    if not transactions_path.exists():
        raise FileNotFoundError(f"Transactions CSV not found: {transactions_path}")
    if not accounts_path.exists():
        raise FileNotFoundError(f"Accounts CSV not found: {accounts_path}")

    LOGGER.info("Starting raw ingestion for AMLGuardian")
    connection = postgres_connection()
    try:
        prepare_raw_tables(connection)
        account_rows = ingest_accounts(connection, accounts_path, ingested_at)
        transaction_rows = ingest_transactions(connection, transactions_path, ingested_at)
        post_load_housekeeping(connection)
        LOGGER.info(
            "Ingestion finished successfully | accounts=%s | transactions=%s",
            account_rows,
            transaction_rows,
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

