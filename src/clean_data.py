from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

FX_RATES_TO_EUR = {
    "EUR": 1.0,
    "USD": 0.92,
    "GBP": 1.17,
}


def clean_accounts(accounts: pd.DataFrame) -> pd.DataFrame:
    accounts = accounts.copy()
    accounts = accounts.rename(columns={"name": "account_name"})

    required = ["account_id", "account_name", "country", "account_type"]
    missing = [column for column in required if column not in accounts.columns]
    if missing:
        raise ValueError(f"Missing account columns: {missing}")

    accounts["account_id"] = accounts["account_id"].astype(str).str.strip()
    accounts["account_name"] = accounts["account_name"].fillna("UNKNOWN").astype(str).str.strip()
    accounts["country"] = accounts["country"].fillna("UNKNOWN").astype(str).str.upper().str.strip()
    accounts["account_type"] = accounts["account_type"].fillna("UNKNOWN").astype(str).str.upper().str.strip()

    accounts = accounts[accounts["account_id"] != ""]
    accounts = accounts.drop_duplicates(subset=["account_id"], keep="first")
    return accounts[required]


def clean_transactions(transactions: pd.DataFrame) -> pd.DataFrame:
    transactions = transactions.copy()
    transactions = transactions.rename(
        columns={
            "timestamp": "transaction_timestamp",
            "amount": "amount_original",
        }
    )

    required = [
        "transaction_id",
        "transaction_timestamp",
        "sender_account_id",
        "receiver_account_id",
        "amount_original",
        "currency",
        "transaction_type",
    ]
    missing = [column for column in required if column not in transactions.columns]
    if missing:
        raise ValueError(f"Missing transaction columns: {missing}")

    text_columns = ["transaction_id", "sender_account_id", "receiver_account_id"]
    for column in text_columns:
        transactions[column] = transactions[column].astype(str).str.strip()

    transactions["currency"] = transactions["currency"].fillna("EUR").astype(str).str.upper().str.strip()
    transactions["transaction_type"] = (
        transactions["transaction_type"].fillna("UNKNOWN").astype(str).str.upper().str.strip()
    )
    transactions["amount_original"] = pd.to_numeric(transactions["amount_original"], errors="coerce")
    transactions["amount_eur"] = (
        transactions["amount_original"] * transactions["currency"].map(FX_RATES_TO_EUR).fillna(1.0)
    ).round(2)
    transactions["transaction_timestamp"] = pd.to_datetime(
        transactions["transaction_timestamp"], errors="coerce", utc=True
    )
    transactions["transaction_date"] = transactions["transaction_timestamp"].dt.date.astype(str)

    if "is_laundering" in transactions.columns:
        transactions["is_laundering"] = (
            pd.to_numeric(transactions["is_laundering"], errors="coerce").fillna(0).astype(int)
        )
    else:
        transactions["is_laundering"] = 0

    before = len(transactions)
    transactions = transactions.dropna(subset=["transaction_timestamp", "amount_eur"])
    transactions = transactions[
        (transactions["transaction_id"] != "")
        & (transactions["sender_account_id"] != "")
        & (transactions["receiver_account_id"] != "")
        & (transactions["amount_eur"] > 0)
    ]
    transactions = transactions.drop_duplicates(subset=["transaction_id"], keep="first")
    dropped = before - len(transactions)
    if dropped:
        print(f"Dropped {dropped} invalid or duplicate transactions.")

    return transactions[
        [
            "transaction_id",
            "transaction_timestamp",
            "transaction_date",
            "sender_account_id",
            "receiver_account_id",
            "amount_original",
            "amount_eur",
            "currency",
            "transaction_type",
            "is_laundering",
        ]
    ]


def main() -> None:
    accounts = pd.read_csv(PROCESSED_DIR / "accounts_ingested.csv")
    transactions = pd.read_csv(PROCESSED_DIR / "transactions_ingested.csv")

    clean_accounts(accounts).to_csv(PROCESSED_DIR / "accounts_clean.csv", index=False)
    clean_transactions(transactions).to_csv(PROCESSED_DIR / "transactions_clean.csv", index=False)

    print("Clean data saved in data/processed/.")


if __name__ == "__main__":
    main()
