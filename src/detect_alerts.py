from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

SMURFING_THRESHOLD = 9_999
SMURFING_MIN_TXNS = 5
FAN_MIN_COUNTERPARTIES = 5

HIGH_RISK_COUNTRIES = {"IRAN", "MYANMAR", "DPRK", "SYRIA", "YEMEN"}

REASON_CODES = {
    "SMURFING": "Potential structuring pattern",
    "FAN_IN": "Repeated transactions in short period",
    "FAN_OUT": "Unusual transaction pattern",
    "HIGH_RISK_GEOGRAPHY": "High-risk rule match",
}


def make_alert_id(account_id: str, rule_name: str, window_end: pd.Timestamp) -> str:
    raw = f"{account_id}|{rule_name}|{window_end.isoformat()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def severity_from_count(count: int) -> str:
    if count >= 10:
        return "HIGH"
    if count >= 5:
        return "MEDIUM"
    return "LOW"


def reason_code_for_rule(rule_name: str) -> str:
    return REASON_CODES.get(rule_name, "Unusual transaction pattern")


def build_alert(
    account_id: str,
    rule_name: str,
    severity: str,
    reason: str,
    metric_1_name: str,
    metric_1_value: object,
    metric_2_name: str,
    metric_2_value: object,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> dict[str, object]:
    return {
        "alert_id": make_alert_id(account_id, rule_name, window_end),
        "account_id": account_id,
        "rule_name": rule_name,
        "rule_triggered": rule_name,
        "severity": severity,
        "reason_code": reason_code_for_rule(rule_name),
        "reason": reason,
        "status": "Open for review",
        "metric_1_name": metric_1_name,
        "metric_1_value": metric_1_value,
        "metric_2_name": metric_2_name,
        "metric_2_value": metric_2_value,
        "detection_window_start": window_start.isoformat(),
        "detection_window_end": window_end.isoformat(),
        "detection_date": window_end.date().isoformat(),
    }


def detect_smurfing(transactions: pd.DataFrame) -> list[dict[str, object]]:
    alerts = []
    candidates = transactions[transactions["amount_eur"] < SMURFING_THRESHOLD].copy()
    for account_id, group in candidates.groupby("sender_account_id"):
        group = group.sort_values("transaction_timestamp")
        best_window = None
        for _, row in group.iterrows():
            window_start = row["transaction_timestamp"]
            window_end = window_start + pd.Timedelta(hours=72)
            window = group[
                (group["transaction_timestamp"] >= window_start)
                & (group["transaction_timestamp"] <= window_end)
            ]
            if len(window) >= SMURFING_MIN_TXNS:
                total_amount = round(window["amount_eur"].sum(), 2)
                candidate = (len(window), total_amount, window_start, window["transaction_timestamp"].max())
                if best_window is None or candidate[:2] > best_window[:2]:
                    best_window = candidate
        if best_window:
            count, total_amount, window_start, window_end = best_window
            alerts.append(
                build_alert(
                    account_id=account_id,
                    rule_name="SMURFING",
                    severity=severity_from_count(count),
                    reason=(
                        f"Account sent {count} transfers below EUR {SMURFING_THRESHOLD} "
                        "within 72 hours; this may indicate structuring and requires review."
                    ),
                    metric_1_name="transaction_count_72h",
                    metric_1_value=count,
                    metric_2_name="amount_72h_eur",
                    metric_2_value=total_amount,
                    window_start=window_start,
                    window_end=window_end,
                )
            )
    return alerts


def detect_fan_pattern(
    transactions: pd.DataFrame,
    account_column: str,
    counterparty_column: str,
    rule_name: str,
    direction_label: str,
) -> list[dict[str, object]]:
    alerts = []
    for account_id, group in transactions.groupby(account_column):
        group = group.sort_values("transaction_timestamp")
        best_window = None
        for _, row in group.iterrows():
            window_start = row["transaction_timestamp"]
            window_end = window_start + pd.Timedelta(hours=24)
            window = group[
                (group["transaction_timestamp"] >= window_start)
                & (group["transaction_timestamp"] <= window_end)
            ]
            unique_counterparties = window[counterparty_column].nunique()
            if unique_counterparties >= FAN_MIN_COUNTERPARTIES:
                total_amount = round(window["amount_eur"].sum(), 2)
                candidate = (
                    unique_counterparties,
                    total_amount,
                    window_start,
                    window["transaction_timestamp"].max(),
                )
                if best_window is None or candidate[:2] > best_window[:2]:
                    best_window = candidate
        if best_window:
            unique_counterparties, total_amount, window_start, window_end = best_window
            alerts.append(
                build_alert(
                    account_id=account_id,
                    rule_name=rule_name,
                    severity=severity_from_count(unique_counterparties),
                    reason=(
                        f"Account {direction_label} {unique_counterparties} unique counterparties "
                        "within 24 hours; this may indicate unusual movement for review."
                    ),
                    metric_1_name="unique_counterparties_24h",
                    metric_1_value=unique_counterparties,
                    metric_2_name="amount_24h_eur",
                    metric_2_value=total_amount,
                    window_start=window_start,
                    window_end=window_end,
                )
            )
    return alerts


def detect_high_risk_geography(transactions: pd.DataFrame) -> list[dict[str, object]]:
    alerts = []
    flagged = transactions[
        transactions["sender_country"].isin(HIGH_RISK_COUNTRIES)
        | transactions["receiver_country"].isin(HIGH_RISK_COUNTRIES)
    ].copy()
    if flagged.empty:
        return alerts

    account_rows = pd.concat(
        [
            flagged.rename(columns={"sender_account_id": "account_id"})[
                ["account_id", "transaction_timestamp", "amount_eur", "sender_country", "receiver_country"]
            ],
            flagged.rename(columns={"receiver_account_id": "account_id"})[
                ["account_id", "transaction_timestamp", "amount_eur", "sender_country", "receiver_country"]
            ],
        ],
        ignore_index=True,
    )

    for account_id, group in account_rows.groupby("account_id"):
        risky_countries = sorted(
            set(group["sender_country"]).union(set(group["receiver_country"])) & HIGH_RISK_COUNTRIES
        )
        window_start = group["transaction_timestamp"].min()
        window_end = group["transaction_timestamp"].max()
        exposure_count = len(group)
        alerts.append(
            build_alert(
                account_id=account_id,
                rule_name="HIGH_RISK_GEOGRAPHY",
                severity=severity_from_count(exposure_count),
                reason=(
                    "Account transacted with a training watchlist country "
                    f"({', '.join(risky_countries)}); this requires further context review."
                ),
                metric_1_name="high_risk_transfer_count",
                metric_1_value=exposure_count,
                metric_2_name="high_risk_amount_eur",
                metric_2_value=round(group["amount_eur"].sum(), 2),
                window_start=window_start,
                window_end=window_end,
            )
        )
    return alerts


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    transactions = pd.read_csv(PROCESSED_DIR / "transaction_features.csv")
    transactions["transaction_timestamp"] = pd.to_datetime(
        transactions["transaction_timestamp"], utc=True
    )

    alerts = []
    alerts.extend(detect_smurfing(transactions))
    alerts.extend(
        detect_fan_pattern(
            transactions,
            account_column="receiver_account_id",
            counterparty_column="sender_account_id",
            rule_name="FAN_IN",
            direction_label="received funds from",
        )
    )
    alerts.extend(
        detect_fan_pattern(
            transactions,
            account_column="sender_account_id",
            counterparty_column="receiver_account_id",
            rule_name="FAN_OUT",
            direction_label="sent funds to",
        )
    )
    alerts.extend(detect_high_risk_geography(transactions))

    alerts_df = pd.DataFrame(alerts)
    alerts_df = alerts_df.sort_values(["severity", "rule_name", "account_id"])
    alerts_df.to_csv(OUTPUT_DIR / "alerts_sample.csv", index=False)

    print(f"Generated {len(alerts_df)} alerts in outputs/alerts_sample.csv.")


if __name__ == "__main__":
    main()
