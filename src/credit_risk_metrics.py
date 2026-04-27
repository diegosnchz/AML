from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

REQUIRED_LOAN_COLUMNS = [
    "loan_id",
    "customer_id",
    "product_type",
    "origination_date",
    "outstanding_balance",
    "days_past_due",
    "pd",
    "ead",
    "lgd",
    "recovered_amount",
    "status",
]


def delinquency_bucket(days_past_due: int | float) -> str:
    days = int(max(days_past_due, 0))
    if days > 90:
        return "90+ DPD"
    if days >= 61:
        return "61-90 DPD"
    if days >= 31:
        return "31-60 DPD"
    if days >= 1:
        return "1-30 DPD"
    return "CURRENT"


def build_credit_risk_metrics(loans: pd.DataFrame, stress_multiplier: float = 1.5) -> pd.DataFrame:
    missing_columns = [column for column in REQUIRED_LOAN_COLUMNS if column not in loans.columns]
    if missing_columns:
        raise ValueError(f"Missing loan columns: {missing_columns}")

    credit = loans[REQUIRED_LOAN_COLUMNS].copy()

    text_columns = ["loan_id", "customer_id", "product_type", "status"]
    for column in text_columns:
        credit[column] = credit[column].fillna("").astype(str).str.strip()

    credit["origination_date"] = pd.to_datetime(credit["origination_date"], errors="coerce").dt.date

    numeric_columns = ["outstanding_balance", "days_past_due", "pd", "ead", "lgd", "recovered_amount"]
    for column in numeric_columns:
        credit[column] = pd.to_numeric(credit[column], errors="coerce").fillna(0)

    credit["outstanding_balance"] = credit["outstanding_balance"].clip(lower=0)
    credit["days_past_due"] = credit["days_past_due"].clip(lower=0).astype(int)
    credit["pd"] = credit["pd"].clip(lower=0, upper=1)
    credit["ead"] = credit["ead"].clip(lower=0)
    credit["lgd"] = credit["lgd"].clip(lower=0, upper=1)
    credit["recovered_amount"] = credit["recovered_amount"].clip(lower=0)

    multiplier = max(float(stress_multiplier), 0)
    credit["delinquency_bucket"] = credit["days_past_due"].apply(delinquency_bucket)
    credit["npl_flag"] = credit["days_past_due"] > 90
    credit["early_warning_flag"] = credit["days_past_due"].between(30, 90)
    credit["expected_loss"] = (credit["pd"] * credit["ead"] * credit["lgd"]).round(2)
    credit["recovery_rate"] = (credit["recovered_amount"] / credit["ead"]).where(credit["ead"] > 0, 0).round(4)
    credit["stressed_pd"] = (credit["pd"] * multiplier).clip(upper=1).round(4)
    credit["stressed_expected_loss"] = (credit["stressed_pd"] * credit["ead"] * credit["lgd"]).round(2)

    return credit


def save_credit_risk_metrics(
    raw_path: Path = RAW_DIR / "loans.csv",
    output_path: Path = PROCESSED_DIR / "credit_risk_metrics.csv",
    stress_multiplier: float = 1.5,
) -> pd.DataFrame:
    loans = pd.read_csv(raw_path)
    credit = build_credit_risk_metrics(loans, stress_multiplier=stress_multiplier)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    credit.to_csv(output_path, index=False)
    return credit


def main() -> None:
    credit = save_credit_risk_metrics()
    print(
        "Generated data/processed/credit_risk_metrics.csv "
        f"for {len(credit)} loans. Expected loss: EUR {credit['expected_loss'].sum():,.2f}; "
        f"stressed expected loss: EUR {credit['stressed_expected_loss'].sum():,.2f}."
    )


if __name__ == "__main__":
    main()
