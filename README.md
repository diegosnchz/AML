# AML Transaction Monitoring Analytics

AML Transaction Monitoring Analytics is a simplified AML transaction monitoring analytics project. It uses synthetic transaction and account data to practice SQL, Python, alert logic and dashboarding in a realistic junior data analytics portfolio context.

This is an educational portfolio project using synthetic data. It is not a production AML system and does not make real compliance decisions.

One-sentence explanation:

> A simplified AML analytics project that uses Python and SQL to generate explainable rule-based alerts from synthetic transaction data.

## Business Problem

Financial institutions need to monitor transactions and identify patterns that may indicate suspicious activity. In a real team, alerts would be reviewed by analysts together with KYC, customer context and internal procedures.

This project focuses on the analytics layer: cleaning transaction data, creating basic behavioural features and generating explainable alerts that could be used for investigation or dashboarding practice.

The repository is aimed at junior roles such as:

- Junior Data Analyst
- BI Analyst
- Risk / AML Analytics Junior
- Financial Crime Analytics Junior
- Data Quality / Data Management Junior

## What the Project Does

- Loads synthetic account and transaction CSV files.
- Cleans and standardizes column names, dates, currencies and missing values.
- Generates account-level and transaction-level features.
- Applies a small set of explainable rule-based detection scenarios.
- Produces an alerts CSV ready for analyst review or a simple dashboard.

## Detection Rules

The main project keeps the detection logic intentionally simple:

- **Smurfing / structuring:** several outgoing transfers below a threshold within a short time window.
- **Fan-in:** one account receives funds from several unique originators within 24 hours.
- **Fan-out:** one account sends funds to several unique beneficiaries within 24 hours.
- **High-risk geography:** an account transacts with a country included in a small watchlist for training purposes.
- **Optional advanced SQL:** a circular flow example is included in SQL as future practice, not as part of the core Python pipeline.

Each alert includes an `alert_id`, `account_id`, `rule_name`, `severity`, `reason`, supporting metrics and a detection date or window.

## Tech Stack

Main stack:

- Python
- Pandas
- SQL
- CSV files for input/output

Optional or archived work is kept under `experimental/` for future learning. It is not required to run the simplified project.

## Repository Layout

```text
AML/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/
│   └── processed/
├── src/
│   ├── ingest_data.py
│   ├── clean_data.py
│   ├── generate_features.py
│   └── detect_alerts.py
├── sql/
│   ├── 01_create_tables.sql
│   ├── 02_account_features.sql
│   └── 03_detection_rules.sql
├── outputs/
│   └── alerts_sample.csv
├── docs/
│   ├── methodology.md
│   └── case_studies.md
└── experimental/
    ├── ml_scoring/
    ├── graph_analytics/
    ├── orchestration/
    └── archive_docs/
```

## How to Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the simple pipeline:

```bash
python src/ingest_data.py
python src/clean_data.py
python src/generate_features.py
python src/detect_alerts.py
```

Input files:

- `data/raw/accounts.csv`
- `data/raw/transactions.csv`

Generated files:

- `data/processed/accounts_ingested.csv`
- `data/processed/transactions_ingested.csv`
- `data/processed/accounts_clean.csv`
- `data/processed/transactions_clean.csv`
- `data/processed/account_features.csv`
- `data/processed/transaction_features.csv`
- `outputs/alerts_sample.csv`

## Risk Reporting & BI Demo

This repository also includes a small Streamlit dashboard called **Risk Reporting & BI Demo**. It is designed as a personal/academic interview demo, not as a real banking system.

What it shows:

- a simple transactional data pipeline,
- basic data quality checks,
- explainable rule-based alerts,
- risk/reporting KPIs,
- visual monitoring charts,
- an alert review table with business-friendly reason codes,
- a short Spanish interview script inside the dashboard.

Technologies used:

- Python
- Pandas
- Streamlit
- CSV files

Run it from the repository root:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python src/ingest_data.py
python src/clean_data.py
python src/generate_features.py
python src/detect_alerts.py

streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal, usually:

```text
http://localhost:8501
```

The demo is intentionally small and explainable. It uses synthetic data and fixed rules so it can be presented in a 2-3 minute interview walkthrough.

## Outputs

The final alerts table contains:

- alert identifier
- account identifier
- rule name
- severity
- short reason for review
- supporting metrics
- detection window

The alerts are not final conclusions. They show patterns that may indicate unusual behaviour and would require further review by an analyst.

## Case Studies

### Case 1: Repeated Smaller Outbound Transfers

An account receives a larger inbound transfer and then sends several smaller payments to different beneficiaries over the next two days. The smurfing rule may indicate possible structuring because the payments are split into multiple lower-value transfers.

This would be escalated to an analyst for review of customer profile, expected activity and relationship with the beneficiaries.

### Case 2: Collection Account Behaviour

Another account receives payments from several unrelated originators within a short time window. The fan-in rule may indicate that the account is acting as a collection point.

The alert does not prove suspicious activity. It highlights a pattern that requires further review, especially if the account profile does not explain that volume or number of counterparties.

More detailed examples are available in `docs/case_studies.md`.

## Future Improvements

The following ideas are intentionally outside the main junior-friendly path:

- Airflow orchestration for scheduled runs.
- Graph analytics for network exploration.
- ML risk scoring as an optional experiment.
- Model explanation techniques as future learning.
- Analyst feedback loop to mark reviewed alerts and improve rules.

Advanced or previous work has been moved to `experimental/` so the main project stays easy to understand.
