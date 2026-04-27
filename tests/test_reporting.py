from __future__ import annotations

import unittest

import pandas as pd

from src.reporting import (
    add_alert_business_fields,
    calculate_reporting_metrics,
    data_quality_summary,
)


class ReportingTests(unittest.TestCase):
    def test_alert_rate_uses_alerts_over_transactions(self) -> None:
        transactions = pd.DataFrame(
            {
                "transaction_id": ["T1", "T2", "T3", "T4"],
                "transaction_timestamp": pd.to_datetime(
                    ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"], utc=True
                ),
                "sender_account_id": ["A1", "A1", "A2", "A3"],
                "receiver_account_id": ["A2", "A3", "A3", "A4"],
            }
        )
        alerts = pd.DataFrame(
            {
                "alert_id": ["AL1"],
                "account_id": ["A1"],
                "rule_name": ["SMURFING"],
                "severity": ["MEDIUM"],
                "metric_2_name": ["amount_72h_eur"],
                "metric_2_value": [1000],
                "detection_date": ["2024-01-02"],
            }
        )
        dq = pd.DataFrame([{"check": "missing key fields", "issues": 0, "detail": ""}])

        metrics = calculate_reporting_metrics(transactions, alerts, dq)

        self.assertEqual(metrics["total_transactions"], 4)
        self.assertEqual(metrics["total_alerts"], 1)
        self.assertEqual(metrics["alert_rate"], 0.25)

    def test_data_quality_checks_detect_basic_issues(self) -> None:
        raw = pd.DataFrame(
            {
                "transaction_id": ["T1", "T1", "T3"],
                "timestamp": ["2024-01-01T10:00:00Z", "bad-date", "2024-01-02T10:00:00Z"],
                "sender_account_id": ["A1", "A1", ""],
                "receiver_account_id": ["A2", "A2", "A4"],
                "amount": [100, -50, 25],
                "currency": ["EUR", "EUR", "EUR"],
                "transaction_type": ["TRANSFER", "TRANSFER", "TRANSFER"],
            }
        )

        summary = data_quality_summary(raw)
        issues = dict(zip(summary["check"], summary["issues"]))

        self.assertEqual(issues["missing key fields"], 1)
        self.assertEqual(issues["duplicated transaction IDs"], 2)
        self.assertEqual(issues["invalid dates"], 1)
        self.assertEqual(issues["zero or negative amounts"], 1)

    def test_reason_codes_are_added_for_known_rules(self) -> None:
        alerts = pd.DataFrame({"rule_name": ["SMURFING", "FAN_IN", "HIGH_RISK_GEOGRAPHY"]})

        enriched = add_alert_business_fields(alerts)

        self.assertIn("reason_code", enriched.columns)
        self.assertEqual(enriched.loc[0, "reason_code"], "Potential structuring pattern")
        self.assertEqual(enriched.loc[1, "reason_code"], "Repeated transactions in short period")
        self.assertEqual(enriched.loc[2, "reason_code"], "High-risk rule match")


if __name__ == "__main__":
    unittest.main()
