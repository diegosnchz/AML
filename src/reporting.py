from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

EXPECTED_TRANSACTION_TYPES = {"WIRE_IN", "TRANSFER"}
EXPECTED_CURRENCIES = {"EUR", "USD", "GBP"}
ALERT_AMOUNT_METRICS = {"amount_72h_eur", "amount_24h_eur", "high_risk_amount_eur"}

REASON_CODES = {
    "SMURFING": "Potential structuring pattern",
    "FAN_IN": "Repeated transactions in short period",
    "FAN_OUT": "Unusual transaction pattern",
    "HIGH_RISK_GEOGRAPHY": "High-risk rule match",
}


def load_demo_tables(
    processed_dir: Path = PROCESSED_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    accounts = pd.read_csv(processed_dir / "accounts_clean.csv")
    transactions = pd.read_csv(processed_dir / "transaction_features.csv")
    alerts = pd.read_csv(output_dir / "alerts_sample.csv")
    return accounts, transactions, alerts


def add_alert_business_fields(alerts: pd.DataFrame) -> pd.DataFrame:
    alerts = alerts.copy()
    alerts["rule_triggered"] = alerts.get("rule_triggered", alerts["rule_name"])
    alerts["reason_code"] = alerts.get("reason_code", alerts["rule_name"].map(REASON_CODES))
    alerts["reason_code"] = alerts["reason_code"].fillna("Unusual transaction pattern")
    alerts["status"] = alerts.get("status", "Open for review")
    return alerts


def data_quality_summary(transactions_raw: pd.DataFrame) -> pd.DataFrame:
    required = [
        "transaction_id",
        "timestamp",
        "sender_account_id",
        "receiver_account_id",
        "amount",
        "currency",
        "transaction_type",
    ]
    missing_columns = [column for column in required if column not in transactions_raw.columns]
    if missing_columns:
        return pd.DataFrame(
            [{"check": "required columns present", "issues": len(missing_columns), "detail": ", ".join(missing_columns)}]
        )

    transactions = transactions_raw.copy()
    key_fields = ["transaction_id", "timestamp", "sender_account_id", "receiver_account_id", "amount"]
    missing_key_fields = transactions[key_fields].isna().any(axis=1) | (
        transactions[key_fields].astype(str).apply(lambda column: column.str.strip()).eq("").any(axis=1)
    )

    parsed_dates = pd.to_datetime(transactions["timestamp"], errors="coerce", utc=True)
    amounts = pd.to_numeric(transactions["amount"], errors="coerce")
    duplicated_transaction_ids = transactions["transaction_id"].duplicated(keep=False)
    unexpected_categories = (
        ~transactions["transaction_type"].fillna("").astype(str).str.upper().isin(EXPECTED_TRANSACTION_TYPES)
        | ~transactions["currency"].fillna("").astype(str).str.upper().isin(EXPECTED_CURRENCIES)
    )

    rows = [
        {
            "check": "missing key fields",
            "issues": int(missing_key_fields.sum()),
            "detail": "transaction_id, timestamp, accounts and amount should be present",
        },
        {
            "check": "duplicated transaction IDs",
            "issues": int(duplicated_transaction_ids.sum()),
            "detail": "duplicate IDs can distort counts and alert evidence",
        },
        {
            "check": "invalid dates",
            "issues": int(parsed_dates.isna().sum()),
            "detail": "timestamps must be parseable for time-window rules",
        },
        {
            "check": "zero or negative amounts",
            "issues": int(((amounts <= 0) | amounts.isna()).sum()),
            "detail": "amounts are expected to be positive in this demo",
        },
        {
            "check": "unexpected categories/statuses",
            "issues": int(unexpected_categories.sum()),
            "detail": "currency and transaction_type are checked against a small demo list",
        },
    ]
    return pd.DataFrame(rows)


def calculate_reporting_metrics(
    transactions: pd.DataFrame,
    alerts: pd.DataFrame,
    dq_summary: pd.DataFrame,
) -> dict[str, object]:
    alerts = add_alert_business_fields(alerts)
    transactions = transactions.copy()
    transactions["transaction_timestamp"] = pd.to_datetime(
        transactions["transaction_timestamp"], errors="coerce", utc=True
    )

    alert_amounts = pd.to_numeric(
        alerts["metric_2_value"].where(alerts["metric_2_name"].isin(ALERT_AMOUNT_METRICS), 0),
        errors="coerce",
    ).fillna(0)
    total_alert_amount = float(alert_amounts.sum())
    total_transactions = int(len(transactions))
    total_alerts = int(len(alerts))

    all_accounts = pd.concat(
        [transactions["sender_account_id"], transactions["receiver_account_id"]],
        ignore_index=True,
    )

    alerts_over_time = (
        alerts.assign(alert_amount=alert_amounts)
        .groupby("detection_date", as_index=False)
        .agg(total_alert_amount=("alert_amount", "sum"), total_alerts=("alert_id", "count"))
        .sort_values("detection_date")
    )

    return {
        "total_transactions": total_transactions,
        "total_alerts": total_alerts,
        "alert_rate": total_alerts / total_transactions if total_transactions else 0,
        "total_alert_amount": total_alert_amount,
        "avg_alert_amount": total_alert_amount / total_alerts if total_alerts else 0,
        "unique_customers_accounts": int(all_accounts.nunique()),
        "data_quality_issues_detected": int(dq_summary["issues"].sum()),
        "alerts_by_severity": alerts.groupby("severity", as_index=False).size().rename(columns={"size": "alerts"}),
        "alerts_by_rule": alerts.groupby("rule_triggered", as_index=False).size().rename(columns={"size": "alerts"}),
        "alerts_over_time": alerts_over_time,
        "top_customers_by_alert_amount": (
            alerts.assign(alert_amount=alert_amounts)
            .groupby("account_id", as_index=False)["alert_amount"]
            .sum()
            .sort_values("alert_amount", ascending=False)
            .head(10)
        ),
        "data_quality_summary": dq_summary,
    }


def build_alert_review_table(alerts: pd.DataFrame, transactions: pd.DataFrame) -> pd.DataFrame:
    alerts = add_alert_business_fields(alerts)
    transactions = transactions.copy()
    transactions["transaction_timestamp"] = pd.to_datetime(
        transactions["transaction_timestamp"], errors="coerce", utc=True
    )

    rows: list[dict[str, object]] = []
    for _, alert in alerts.iterrows():
        window_start = pd.to_datetime(alert["detection_window_start"], utc=True)
        window_end = pd.to_datetime(alert["detection_window_end"], utc=True)
        account_id = alert["account_id"]
        evidence = transactions[
            (
                (transactions["sender_account_id"] == account_id)
                | (transactions["receiver_account_id"] == account_id)
            )
            & (transactions["transaction_timestamp"] >= window_start)
            & (transactions["transaction_timestamp"] <= window_end)
        ]

        for _, transaction in evidence.iterrows():
            rows.append(
                {
                    "transaction_id": transaction["transaction_id"],
                    "account_id": account_id,
                    "date": transaction["transaction_timestamp"].date().isoformat(),
                    "amount": float(transaction["amount_eur"]),
                    "rule_triggered": alert["rule_triggered"],
                    "severity": alert["severity"],
                    "reason_code": alert["reason_code"],
                    "status": alert["status"],
                }
            )

    columns = [
        "transaction_id",
        "account_id",
        "date",
        "amount",
        "rule_triggered",
        "severity",
        "reason_code",
        "status",
    ]
    return pd.DataFrame(rows, columns=columns)
