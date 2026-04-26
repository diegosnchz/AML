from __future__ import annotations

import csv
import os
import re
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "docs" / "export"
MARKDOWN_OUTPUT = EXPORT_DIR / "AML_project_full_study_pack.md"
PDF_OUTPUT = EXPORT_DIR / "AML_project_full_study_pack.pdf"

TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".sql",
    ".csv",
    ".txt",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
}
SPECIAL_TEXT_FILENAMES = {
    "README.md",
    "requirements.txt",
    "LICENSE",
    ".env.example",
    ".gitignore",
}
EXCLUDED_DIRS = {
    ".git",
    ".claude",
    ".tools",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "aml-interview-demo",
}
EXCLUDED_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".zip",
    ".parquet",
    ".db",
    ".sqlite",
    ".pkl",
    ".joblib",
    ".pyc",
}
MAX_FULL_TEXT_BYTES = 180_000
MAX_CSV_FULL_ROWS = 50
CSV_SAMPLE_ROWS = 20


@dataclass
class FileRecord:
    path: Path
    rel_path: str
    size_bytes: int
    source: str


@dataclass
class SkippedFile:
    rel_path: str
    reason: str


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def should_exclude_path(path: Path) -> str | None:
    parts = set(path.relative_to(PROJECT_ROOT).parts)
    ignored_parts = parts & EXCLUDED_DIRS
    if ignored_parts:
        return f"excluded directory: {', '.join(sorted(ignored_parts))}"
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return f"excluded binary/heavy suffix: {path.suffix.lower()}"
    if path.name == ".env":
        return "local environment file excluded to avoid exporting secrets"
    if path == MARKDOWN_OUTPUT or path == PDF_OUTPUT:
        return "generated export output"
    return None


def is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in SPECIAL_TEXT_FILENAMES


def git_tracked_files() -> set[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    except Exception:
        return set()


def discover_files() -> tuple[list[FileRecord], list[SkippedFile]]:
    tracked = git_tracked_files()
    records: dict[str, FileRecord] = {}
    skipped: list[SkippedFile] = []

    for root, dirnames, filenames in os.walk(PROJECT_ROOT):
        root_path = Path(root)
        kept_dirnames = []
        for dirname in dirnames:
            directory_path = root_path / dirname
            directory_rel = rel(directory_path)
            if dirname in EXCLUDED_DIRS:
                skipped.append(SkippedFile(f"{directory_rel}/", f"excluded directory: {dirname}"))
            else:
                kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames

        for filename in filenames:
            path = root_path / filename
            if not path.is_file():
                continue

            rel_path = rel(path)
            exclusion_reason = should_exclude_path(path)
            if exclusion_reason:
                skipped.append(SkippedFile(rel_path, exclusion_reason))
                continue

            if not is_text_candidate(path):
                skipped.append(SkippedFile(rel_path, "not an included text type"))
                continue

            size_bytes = path.stat().st_size
            if size_bytes > MAX_FULL_TEXT_BYTES and path.suffix.lower() != ".csv":
                skipped.append(SkippedFile(rel_path, f"text file too large: {size_bytes} bytes"))
                continue

            source = "tracked" if rel_path in tracked else "local-generated"
            records[rel_path] = FileRecord(path=path, rel_path=rel_path, size_bytes=size_bytes, source=source)

    priority_prefixes = {
        "README.md": 0,
        "requirements.txt": 1,
        "src/": 2,
        "sql/": 3,
        "docs/": 4,
        "data/raw/": 5,
        "data/processed/": 6,
        "outputs/": 7,
        "experimental/": 8,
    }

    def sort_key(record: FileRecord) -> tuple[int, str]:
        for prefix, priority in priority_prefixes.items():
            if record.rel_path == prefix.rstrip("/") or record.rel_path.startswith(prefix):
                return priority, record.rel_path
        return 99, record.rel_path

    return sorted(records.values(), key=sort_key), sorted(skipped, key=lambda item: item.rel_path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def fence_language(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".py": "python",
        ".sql": "sql",
        ".csv": "csv",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".txt": "text",
        ".md": "markdown",
    }.get(suffix, "text")


def heading_anchor(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tree_from_records(records: list[FileRecord]) -> str:
    paths = [record.rel_path for record in records]
    tree: dict[str, dict] = {}
    for path in paths:
        node = tree
        for part in path.split("/"):
            node = node.setdefault(part, {})

    def render(node: dict[str, dict], indent: int = 0) -> list[str]:
        lines: list[str] = []
        for name in sorted(node):
            suffix = "/" if node[name] else ""
            lines.append("  " * indent + name + suffix)
            if node[name]:
                lines.extend(render(node[name], indent + 1))
        return lines

    return "\n".join(render(tree))


def csv_profile(record: FileRecord) -> dict[str, object]:
    rows: list[list[str]] = []
    with record.path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        for index, row in enumerate(reader):
            rows.append(row)
            if index >= CSV_SAMPLE_ROWS:
                break

    row_count = 0
    with record.path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        header_seen = False
        for row in reader:
            if not header_seen:
                header_seen = True
                continue
            if row:
                row_count += 1

    headers = rows[0] if rows else []
    return {"headers": headers, "rows": rows, "row_count": row_count}


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    if not headers:
        return "_No columns detected._"
    safe_headers = [cell.replace("|", "\\|") for cell in headers]
    table = ["| " + " | ".join(safe_headers) + " |"]
    table.append("| " + " | ".join("---" for _ in safe_headers) + " |")
    for row in rows:
        padded = row + [""] * (len(headers) - len(row))
        safe_row = [str(cell).replace("|", "\\|") for cell in padded[: len(headers)]]
        table.append("| " + " | ".join(safe_row) + " |")
    return "\n".join(table)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def infer_data_dictionary(records: list[FileRecord]) -> str:
    descriptions = {
        "account_id": "Unique account identifier; inferred from file/code context.",
        "account_name": "Readable account/customer name after cleaning; inferred from file/code context.",
        "name": "Raw account name before cleaning.",
        "country": "Account country used for geography features.",
        "account_type": "Synthetic type/category of the account.",
        "transaction_id": "Unique transaction identifier.",
        "timestamp": "Raw transaction timestamp.",
        "transaction_timestamp": "Cleaned timestamp parsed as UTC datetime.",
        "transaction_date": "Date derived from the transaction timestamp.",
        "sender_account_id": "Account sending funds.",
        "receiver_account_id": "Account receiving funds.",
        "amount": "Raw transaction amount.",
        "amount_original": "Original transaction amount before conversion.",
        "amount_eur": "Transaction amount normalized to EUR in the simplified pipeline.",
        "currency": "Transaction currency.",
        "transaction_type": "Synthetic transaction category/type.",
        "is_laundering": "Synthetic label included in data; not used as real compliance evidence.",
        "sender_country": "Country joined from the sender account.",
        "receiver_country": "Country joined from the receiver account.",
        "high_risk_jurisdiction_flag": "1 when a transaction/account touches the training watchlist.",
        "transaction_count": "Total count of inbound and outbound transactions.",
        "transaction_count_out": "Count of outgoing transactions for the account.",
        "transaction_count_in": "Count of incoming transactions for the account.",
        "total_outbound_amount": "Total EUR sent by the account.",
        "total_inbound_amount": "Total EUR received by the account.",
        "average_transaction_amount": "Average transaction amount; inferred from generated features.",
        "avg_outbound_amount": "Average EUR amount for outgoing transactions.",
        "avg_inbound_amount": "Average EUR amount for incoming transactions.",
        "unique_counterparties": "Number of distinct counterparties connected to the account.",
        "unique_outbound_counterparties": "Number of distinct receivers for outgoing transactions.",
        "unique_inbound_counterparties": "Number of distinct senders for incoming transactions.",
        "number_of_countries": "Number of distinct counterparty countries.",
        "alert_id": "Generated identifier for an alert.",
        "rule_name": "Name of the detection rule that created the alert.",
        "severity": "Simple priority label derived from count-based thresholds.",
        "reason": "Human-readable explanation of why the alert was generated.",
        "metric_1_name": "Name of the first supporting metric.",
        "metric_1_value": "Value of the first supporting metric.",
        "metric_2_name": "Name of the second supporting metric.",
        "metric_2_value": "Value of the second supporting metric.",
        "detection_window_start": "Start of the rule detection window.",
        "detection_window_end": "End of the rule detection window.",
        "detection_date": "Date associated with the alert window end.",
    }

    lines = []
    csv_records = [record for record in records if record.path.suffix.lower() == ".csv"]
    seen: set[tuple[str, str]] = set()
    for record in csv_records:
        profile = csv_profile(record)
        headers = profile["headers"]
        if not headers:
            continue
        lines.append(f"### {record.rel_path}")
        lines.append("")
        lines.append(f"- Row count: {profile['row_count']}")
        lines.append("- Columns:")
        for column in headers:
            key = (record.rel_path, column)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"  - `{column}`: {descriptions.get(column, 'Meaning inferred from file/code context; no richer definition is explicit in the repository.')}")
        lines.append("")
    return "\n".join(lines)


def rule_examples() -> dict[str, dict[str, str]]:
    rows = load_csv_rows(PROJECT_ROOT / "outputs" / "alerts_sample.csv")
    examples: dict[str, dict[str, str]] = {}
    for row in rows:
        examples.setdefault(row.get("rule_name", ""), row)
    return examples


def format_rule_example(rule_name: str, examples: dict[str, dict[str, str]]) -> str:
    row = examples.get(rule_name)
    if not row:
        return "No example alert found in `outputs/alerts_sample.csv`."
    return (
        f"Example alert: `{row.get('alert_id')}` for account `{row.get('account_id')}`, "
        f"severity `{row.get('severity')}`. Reason: {row.get('reason')}"
    )


def generated_sections(records: list[FileRecord], skipped: list[SkippedFile]) -> str:
    examples = rule_examples()
    return f"""# AML Transaction Monitoring Analytics — Full Study Pack

Generated from repository: `{PROJECT_ROOT}`

## 1. Project Overview

This repository is a simplified AML transaction monitoring analytics project for a junior Data/BI + AML analytics portfolio. It uses synthetic account and transaction CSV files, cleans and standardizes them with Python/Pandas, creates basic behavioural features, applies explainable rule-based alert detection, and produces an alerts CSV for analyst review or dashboarding practice.

The main pipeline is:

1. `src/ingest_data.py`
2. `src/clean_data.py`
3. `src/generate_features.py`
4. `src/detect_alerts.py`

The main output is `outputs/alerts_sample.csv`. The project is educational, uses synthetic data, and does not make real compliance decisions.

Core project = simplified junior analytics project. `experimental/` = optional, archived or future-work material.

## 2. Repository Map

The following tree includes files selected for this study pack:

```text
{tree_from_records(records)}
```

## 3. Execution Flow

### Step 1: `src/ingest_data.py`

- Input files: `data/raw/accounts.csv`, `data/raw/transactions.csv`.
- Output files: `data/processed/accounts_ingested.csv`, `data/processed/transactions_ingested.csv`.
- Main transformations: standardizes column names and adds an ingestion timestamp.
- Why it matters: creates a reproducible first landing layer while keeping the project CSV/Pandas based.

### Step 2: `src/clean_data.py`

- Input files: ingested account and transaction CSVs from `data/processed/`.
- Output files: `data/processed/accounts_clean.csv`, `data/processed/transactions_clean.csv`.
- Main transformations: renames key fields, parses timestamps, normalizes currencies, converts amounts to EUR, handles missing values, filters invalid rows and removes duplicates.
- Why it matters: creates consistent data for reliable features and rules.

### Step 3: `src/generate_features.py`

- Input files: clean account and transaction CSVs.
- Output files: `data/processed/account_features.csv`, `data/processed/transaction_features.csv`.
- Main transformations: joins country context, calculates inbound/outbound totals, transaction counts, unique counterparties, country counts, average amount and a high-risk jurisdiction flag.
- Why it matters: turns raw transactions into analyst-friendly behavioural indicators.

### Step 4: `src/detect_alerts.py`

- Input file: `data/processed/transaction_features.csv`.
- Output file: `outputs/alerts_sample.csv`.
- Main transformations: applies smurfing, fan-in, fan-out and high-risk geography rules.
- Why it matters: produces a final table that can be reviewed by an analyst or used in a dashboard.

## 4. Data Dictionary

The definitions below are generated from CSV headers and code context. When the repository does not define a business meaning explicitly, the description says it is inferred.

{infer_data_dictionary(records)}

## 5. Detection Rules Explained

### Smurfing / Structuring

- Business intuition: repeated smaller outgoing transfers may indicate an attempt to split value into multiple payments.
- Technical logic: `detect_smurfing` checks outgoing transactions below EUR 9,999 and looks for at least 5 within a 72-hour window.
- Input columns: `sender_account_id`, `amount_eur`, `transaction_timestamp`.
- Output columns: `alert_id`, `account_id`, `rule_name`, `severity`, `reason`, supporting metric fields and detection window fields.
- Limitations: fixed thresholds, no customer profile, no historical baseline and no real compliance decision.
- {format_rule_example("SMURFING", examples)}

### Fan-In

- Business intuition: one account receiving funds from many unique originators in a short window may indicate collection-account behaviour.
- Technical logic: `detect_fan_pattern` groups by `receiver_account_id` and counts unique `sender_account_id` values within 24 hours.
- Input columns: `receiver_account_id`, `sender_account_id`, `amount_eur`, `transaction_timestamp`.
- Output columns: same alert schema as other rules.
- Limitations: can be normal for some business accounts; requires profile and activity-context review.
- {format_rule_example("FAN_IN", examples)}

### Fan-Out

- Business intuition: one account sending funds to many unique beneficiaries in a short window may indicate dispersion behaviour.
- Technical logic: `detect_fan_pattern` groups by `sender_account_id` and counts unique `receiver_account_id` values within 24 hours.
- Input columns: `sender_account_id`, `receiver_account_id`, `amount_eur`, `transaction_timestamp`.
- Output columns: same alert schema as other rules.
- Limitations: can be normal for payroll, refunds or supplier payments; further analyst review is required.
- {format_rule_example("FAN_OUT", examples)}

### High-Risk Geography

- Business intuition: activity involving a watchlist country may require extra context.
- Technical logic: `detect_high_risk_geography` checks whether sender or receiver country appears in the training watchlist: `IRAN`, `MYANMAR`, `DPRK`, `SYRIA`, `YEMEN`.
- Input columns: `sender_country`, `receiver_country`, `amount_eur`, account identifiers and timestamp.
- Output columns: same alert schema as other rules.
- Limitations: the country list is hardcoded for training and is not a maintained regulatory source.
- {format_rule_example("HIGH_RISK_GEOGRAPHY", examples)}

### Circular Flow

- Business intuition: A -> B -> C -> A loops can indicate circular movement of funds.
- Technical logic: present as optional SQL practice in `sql/03_detection_rules.sql`, not as part of the core Python pipeline.
- Input columns: sender/receiver account IDs, transaction timestamps and EUR amount.
- Output columns: query result fields such as account path, time window and total loop amount.
- Limitations: marked as advanced practice; not a core junior-project detection rule.

## 6. Main Documentation Files
"""


def file_explanation(record: FileRecord) -> str:
    path = record.rel_path
    explanations = {
        "README.md": "Main project description, positioning, run instructions and scope.",
        "requirements.txt": "Minimal Python dependencies for the simplified pipeline.",
        "src/ingest_data.py": "Loads raw CSV files, standardizes headers and writes the ingested layer.",
        "src/clean_data.py": "Cleans accounts and transactions, parses timestamps and normalizes amounts.",
        "src/generate_features.py": "Builds transaction-level and account-level analytical features.",
        "src/detect_alerts.py": "Applies simplified rule-based AML alert logic and writes the alerts output.",
        "sql/01_create_tables.sql": "Creates simple SQL tables for accounts and transactions.",
        "sql/02_account_features.sql": "Shows SQL logic for account-level features.",
        "sql/03_detection_rules.sql": "Shows SQL examples for simplified detection rules and optional circular flow.",
        "docs/methodology.md": "Explains the project methodology in study-friendly language.",
        "docs/case_studies.md": "Provides realistic junior analyst case narratives.",
        "outputs/alerts_sample.csv": "Final sample alerts table generated by the rule-based pipeline.",
    }
    if path.startswith("data/raw/"):
        return "Small synthetic raw input CSV used by the simplified project."
    if path.startswith("data/processed/"):
        return "Generated processed CSV from the local pipeline run; useful as a study artifact."
    if path.startswith("experimental/"):
        return "Optional/non-core file retained for archived advanced work or future improvements."
    return explanations.get(path, "Relevant repository text file included for study context.")


def append_full_file_section(lines: list[str], record: FileRecord, level: int = 3) -> None:
    hashes = "#" * level
    lines.append(f"{hashes} `{record.rel_path}`")
    lines.append("")
    lines.append(file_explanation(record))
    lines.append("")

    if record.path.suffix.lower() == ".csv":
        profile = csv_profile(record)
        rows = profile["rows"]
        headers = profile["headers"]
        data_rows = rows[1:]
        lines.append(f"- Row count: {profile['row_count']}")
        lines.append(f"- Columns: {', '.join(f'`{column}`' for column in headers) if headers else 'none detected'}")
        lines.append("")
        if profile["row_count"] <= MAX_CSV_FULL_ROWS:
            lines.append("Full CSV content:")
            lines.append("")
            lines.append(f"```csv\n{read_text(record.path).strip()}\n```")
        else:
            lines.append(f"First {CSV_SAMPLE_ROWS} rows:")
            lines.append("")
            lines.append(markdown_table(headers, data_rows[:CSV_SAMPLE_ROWS]))
        lines.append("")
        return

    language = fence_language(record.path)
    content = read_text(record.path).rstrip()
    lines.append(f"```{language}")
    lines.append(content)
    lines.append("```")
    lines.append("")


def build_markdown(records: list[FileRecord], skipped: list[SkippedFile]) -> str:
    lines: list[str] = []
    lines.append(generated_sections(records, skipped))

    doc_records = [
        record
        for record in records
        if record.rel_path == "README.md"
        or (record.rel_path.startswith("docs/") and record.path.suffix.lower() == ".md" and record.rel_path != "docs/export/AML_project_full_study_pack.md")
    ]
    for record in doc_records:
        append_full_file_section(lines, record)

    lines.append("## 7. Source Code")
    lines.append("")
    code_records = [
        record
        for record in records
        if record.rel_path.startswith("src/")
        or record.rel_path.startswith("sql/")
        or record.rel_path == "docs/export/build_project_pdf.py"
        or record.rel_path in {"requirements.txt", ".gitignore"}
    ]
    for record in code_records:
        append_full_file_section(lines, record)

    lines.append("## 8. Data Samples")
    lines.append("")
    data_records = [
        record
        for record in records
        if record.rel_path.startswith("data/raw/")
        or record.rel_path.startswith("data/processed/")
        or record.rel_path.startswith("outputs/")
    ]
    for record in data_records:
        append_full_file_section(lines, record)

    lines.append("## 9. Experimental / Archived Content")
    lines.append("")
    lines.append("The files below are optional/non-core. They preserve previous or advanced work, but the main interview story should stay focused on the simplified CSV/Pandas/SQL rule-based pipeline.")
    lines.append("")
    experimental_records = [record for record in records if record.rel_path.startswith("experimental/")]
    for record in experimental_records:
        append_full_file_section(lines, record, level=3)

    lines.append("## 10. Interview Defense Notes")
    lines.append("")
    lines.append("### 60-second explanation")
    lines.append("")
    lines.append("This is a simplified AML analytics portfolio project using synthetic data. It loads account and transaction CSVs, cleans them with Python/Pandas, creates behavioural features, applies a small set of explainable rules, and outputs an alerts table for analyst review or dashboarding. It is not a compliance decision system; it is a practical project to demonstrate data cleaning, feature engineering, SQL thinking and AML monitoring concepts at junior level.")
    lines.append("")
    lines.append("### Technical decisions")
    lines.append("")
    lines.append("- Kept the main path CSV/Pandas based so it is easy to run and explain.")
    lines.append("- Used explainable rules instead of ML as the core detection approach.")
    lines.append("- Generated both account-level and transaction-level features.")
    lines.append("- Kept SQL examples for interview discussion and BI/database practice.")
    lines.append("- Archived advanced work under `experimental/` instead of deleting it.")
    lines.append("")
    lines.append("### Trade-offs")
    lines.append("")
    lines.append("- Simplicity over orchestration: easier to understand, but not scheduled.")
    lines.append("- Fixed thresholds over adaptive models: explainable, but less flexible.")
    lines.append("- Synthetic data over real data: safe for a portfolio, but less realistic.")
    lines.append("- Rule-based alerts over final decisions: appropriate for education, but limited for real compliance.")
    lines.append("")
    lines.append("### Why the project was simplified")
    lines.append("")
    lines.append("The simplified version is better aligned with junior Data Analyst, BI Analyst and AML Analytics Junior roles. It shows the author understands the data workflow and AML monitoring logic without overstating production readiness.")
    lines.append("")
    lines.append("### Limitations")
    lines.append("")
    lines.append("- No real customer due diligence data.")
    lines.append("- No analyst feedback loop.")
    lines.append("- No live regulatory watchlist refresh.")
    lines.append("- No transaction monitoring calibration process.")
    lines.append("- No production controls, access management or audit workflow.")
    lines.append("")
    lines.append("### Future improvements")
    lines.append("")
    lines.append("- Add a small Streamlit or Power BI dashboard.")
    lines.append("- Add configurable rule thresholds.")
    lines.append("- Add analyst review status fields.")
    lines.append("- Move the SQL examples into SQLite/PostgreSQL exercises.")
    lines.append("- Revisit `experimental/` for orchestration, graph analytics or ML only after the core story is solid.")
    lines.append("")
    lines.append("### Likely interview questions and strong answers")
    lines.append("")
    lines.append("**Q: Is this a real AML system?**  ")
    lines.append("A: No. It is an educational portfolio project using synthetic data. It generates explainable alerts for practice, but it does not make compliance decisions.")
    lines.append("")
    lines.append("**Q: Why rule-based detection instead of ML?**  ")
    lines.append("A: For junior analytics roles, rule-based detection is easier to explain, audit and connect to AML typologies. ML can be future work, but the main learning goal is clean data and transparent alert logic.")
    lines.append("")
    lines.append("**Q: What would you improve first?**  ")
    lines.append("A: I would add configurable thresholds, a small dashboard and an analyst feedback field so reviewed alerts can be tracked.")
    lines.append("")
    lines.append("**Q: What does `severity` mean here?**  ")
    lines.append("A: It is a simple priority label based on rule metrics, not a final risk rating. It helps order alerts for review.")
    lines.append("")
    lines.append("**Q: How would this differ in a real institution?**  ")
    lines.append("A: A real institution would require governance, threshold calibration, KYC context, alert investigation workflow, audit trails, model/rule validation and regulatory procedures.")
    lines.append("")
    lines.append("## 11. Glossary")
    lines.append("")
    glossary = {
        "AML": "Anti-Money Laundering; controls and analysis used to identify and investigate suspicious financial activity.",
        "Transaction monitoring": "Review of transaction activity to detect unusual or potentially suspicious patterns.",
        "Alert": "A record generated by a rule or model that requires review.",
        "Smurfing": "Splitting funds into multiple smaller transactions, often discussed as structuring.",
        "Fan-in": "Many senders transferring into one receiver within a short period.",
        "Fan-out": "One sender transferring to many receivers within a short period.",
        "High-risk geography": "Activity involving a country or jurisdiction that requires additional context or review.",
        "Synthetic data": "Artificial data created for learning or testing, not real customer data.",
        "Feature engineering": "Creating analytical variables from raw data, such as counts, totals or flags.",
        "Severity": "A simple priority label for an alert in this project.",
        "False positive": "An alert that looks unusual by rule logic but is later explained as legitimate.",
        "Analyst review": "Human investigation step where context, customer profile and evidence are assessed.",
    }
    for term, definition in glossary.items():
        lines.append(f"- **{term}:** {definition}")
    lines.append("")

    lines.append("## Skipped Files")
    lines.append("")
    lines.append("The following files were skipped to avoid heavy, binary, irrelevant or sensitive content.")
    lines.append("")
    for item in skipped:
        lines.append(f"- `{item.rel_path}`: {item.reason}")
    lines.append("")
    return "\n".join(lines)


def markdown_to_pdf(markdown_text: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    normal = ParagraphStyle("StudyNormal", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12)
    code = ParagraphStyle("StudyCode", parent=styles["Code"], fontName="Courier", fontSize=6.5, leading=8, textColor=colors.HexColor("#222222"))
    headings = {
        1: ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, leading=22, spaceAfter=10),
        2: ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, leading=18, spaceBefore=8, spaceAfter=6),
        3: ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11, leading=14, spaceBefore=6, spaceAfter=4),
    }

    doc = SimpleDocTemplate(
        str(PDF_OUTPUT),
        pagesize=A4,
        leftMargin=1.3 * cm,
        rightMargin=1.3 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title="AML Transaction Monitoring Analytics Full Study Pack",
    )

    story = []
    in_code = False
    code_lines: list[str] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = " ".join(paragraph_lines).strip()
        paragraph_lines.clear()
        if not text:
            return
        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("**", "")
            .replace("`", "")
        )
        story.append(Paragraph(escaped, normal))
        story.append(Spacer(1, 4))

    def flush_code() -> None:
        if not code_lines:
            return
        chunk = "\n".join(code_lines)
        code_lines.clear()
        wrapped_lines = []
        for line in chunk.splitlines():
            wrapped_lines.extend(textwrap.wrap(line, width=112, replace_whitespace=False, drop_whitespace=False) or [""])
        story.append(Preformatted("\n".join(wrapped_lines), code))
        story.append(Spacer(1, 6))

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_paragraph()
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            flush_paragraph()
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            text = heading_anchor(heading_match.group(2)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if level == 1 and story:
                story.append(PageBreak())
            story.append(Paragraph(text, headings[level]))
            continue

        if line.startswith("|") or line.startswith("- ") or re.match(r"^\d+\.\s", line):
            flush_paragraph()
            clean = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "")
            story.append(Paragraph(clean, normal))
            story.append(Spacer(1, 2))
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    flush_code()
    doc.build(story)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    records, skipped = discover_files()
    markdown_text = build_markdown(records, skipped)
    MARKDOWN_OUTPUT.write_text(markdown_text, encoding="utf-8")
    markdown_to_pdf(markdown_text)

    print(f"Markdown written to: {MARKDOWN_OUTPUT}")
    print(f"PDF written to: {PDF_OUTPUT}")
    print(f"Included files: {len(records)}")
    print(f"Skipped files: {len(skipped)}")


if __name__ == "__main__":
    main()
