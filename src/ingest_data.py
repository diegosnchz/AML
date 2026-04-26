from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def normalize_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()
    dataframe.columns = (
        dataframe.columns.str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    return dataframe


def read_csv(name: str) -> pd.DataFrame:
    path = RAW_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")
    return normalize_columns(pd.read_csv(path))


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ingested_at = datetime.now(timezone.utc).isoformat()

    accounts = read_csv("accounts.csv")
    transactions = read_csv("transactions.csv")

    accounts["ingested_at"] = ingested_at
    transactions["ingested_at"] = ingested_at

    accounts.to_csv(PROCESSED_DIR / "accounts_ingested.csv", index=False)
    transactions.to_csv(PROCESSED_DIR / "transactions_ingested.csv", index=False)

    print(f"Loaded {len(accounts)} accounts and {len(transactions)} transactions.")


if __name__ == "__main__":
    main()
