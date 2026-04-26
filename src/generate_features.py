from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

HIGH_RISK_COUNTRIES = {"IRAN", "MYANMAR", "DPRK", "SYRIA", "YEMEN"}


def add_country_context(transactions: pd.DataFrame, accounts: pd.DataFrame) -> pd.DataFrame:
    account_countries = accounts[["account_id", "country"]]
    transactions = transactions.merge(
        account_countries.rename(columns={"account_id": "sender_account_id", "country": "sender_country"}),
        on="sender_account_id",
        how="left",
    )
    transactions = transactions.merge(
        account_countries.rename(columns={"account_id": "receiver_account_id", "country": "receiver_country"}),
        on="receiver_account_id",
        how="left",
    )
    transactions["sender_country"] = transactions["sender_country"].fillna("UNKNOWN")
    transactions["receiver_country"] = transactions["receiver_country"].fillna("UNKNOWN")
    transactions["high_risk_jurisdiction_flag"] = (
        transactions["sender_country"].isin(HIGH_RISK_COUNTRIES)
        | transactions["receiver_country"].isin(HIGH_RISK_COUNTRIES)
    ).astype(int)
    return transactions


def build_account_features(transactions: pd.DataFrame, accounts: pd.DataFrame) -> pd.DataFrame:
    outbound = transactions.groupby("sender_account_id").agg(
        transaction_count_out=("transaction_id", "count"),
        total_outbound_amount=("amount_eur", "sum"),
        avg_outbound_amount=("amount_eur", "mean"),
        unique_outbound_counterparties=("receiver_account_id", "nunique"),
    )
    inbound = transactions.groupby("receiver_account_id").agg(
        transaction_count_in=("transaction_id", "count"),
        total_inbound_amount=("amount_eur", "sum"),
        avg_inbound_amount=("amount_eur", "mean"),
        unique_inbound_counterparties=("sender_account_id", "nunique"),
    )

    sent_counterparties = transactions.rename(
        columns={
            "sender_account_id": "account_id",
            "receiver_account_id": "counterparty_account_id",
            "receiver_country": "counterparty_country",
        }
    )[["account_id", "counterparty_account_id", "counterparty_country", "high_risk_jurisdiction_flag"]]
    received_counterparties = transactions.rename(
        columns={
            "receiver_account_id": "account_id",
            "sender_account_id": "counterparty_account_id",
            "sender_country": "counterparty_country",
        }
    )[["account_id", "counterparty_account_id", "counterparty_country", "high_risk_jurisdiction_flag"]]
    counterparties = pd.concat([sent_counterparties, received_counterparties], ignore_index=True)
    counterpart_features = counterparties.groupby("account_id").agg(
        unique_counterparties=("counterparty_account_id", "nunique"),
        number_of_countries=("counterparty_country", "nunique"),
        high_risk_jurisdiction_flag=("high_risk_jurisdiction_flag", "max"),
    )

    features = accounts.set_index("account_id").join([outbound, inbound, counterpart_features])
    numeric_columns = [
        "transaction_count_out",
        "total_outbound_amount",
        "avg_outbound_amount",
        "unique_outbound_counterparties",
        "transaction_count_in",
        "total_inbound_amount",
        "avg_inbound_amount",
        "unique_inbound_counterparties",
        "unique_counterparties",
        "number_of_countries",
        "high_risk_jurisdiction_flag",
    ]
    features[numeric_columns] = features[numeric_columns].fillna(0)
    features["transaction_count"] = (
        features["transaction_count_out"] + features["transaction_count_in"]
    ).astype(int)
    features["average_transaction_amount"] = (
        (features["total_outbound_amount"] + features["total_inbound_amount"])
        / features["transaction_count"].replace(0, pd.NA)
    ).fillna(0)

    amount_columns = [
        "total_outbound_amount",
        "avg_outbound_amount",
        "total_inbound_amount",
        "avg_inbound_amount",
        "average_transaction_amount",
    ]
    features[amount_columns] = features[amount_columns].round(2)
    return features.reset_index()


def main() -> None:
    accounts = pd.read_csv(PROCESSED_DIR / "accounts_clean.csv")
    transactions = pd.read_csv(PROCESSED_DIR / "transactions_clean.csv")

    transaction_features = add_country_context(transactions, accounts)
    account_features = build_account_features(transaction_features, accounts)

    transaction_features.to_csv(PROCESSED_DIR / "transaction_features.csv", index=False)
    account_features.to_csv(PROCESSED_DIR / "account_features.csv", index=False)

    print(f"Generated features for {len(account_features)} accounts.")


if __name__ == "__main__":
    main()
