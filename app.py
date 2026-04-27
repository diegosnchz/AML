from __future__ import annotations

import time

import altair as alt
import pandas as pd
import streamlit as st

from src.reporting import (
    RAW_DIR,
    add_alert_business_fields,
    build_alert_review_table,
    calculate_reporting_metrics,
    calculate_credit_risk_metrics,
    credit_data_quality_summary,
    data_quality_summary,
    load_credit_risk_table,
    load_demo_tables,
)


st.set_page_config(page_title="Risk Reporting & BI Demo", layout="wide")

INK = "#191817"
MUTED = "#6f6257"
PAPER = "#f7f1e8"
PANEL = "#fbf7ef"
BORDER = "#d8cec0"
CLAY = "#c45f3c"
GOLD = "#9b7442"
GREEN = "#657b56"
ROSE = "#a84432"
GRID = "#eadfd1"


@st.cache_data
def load_dashboard_data() -> dict[str, object]:
    accounts, transactions, alerts = load_demo_tables()
    raw_transactions = pd.read_csv(RAW_DIR / "transactions.csv")
    dq_summary = data_quality_summary(raw_transactions)
    alerts = add_alert_business_fields(alerts)
    metrics = calculate_reporting_metrics(transactions, alerts, dq_summary)
    review_table = build_alert_review_table(alerts, transactions)
    return {
        "accounts": accounts,
        "transactions": transactions,
        "alerts": alerts,
        "metrics": metrics,
        "review_table": review_table,
    }


def money(value: float) -> str:
    return f"EUR {value:,.2f}"


def pct(value: float) -> str:
    return f"{value:.1%}"


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        :root {{
            --ink: {INK};
            --muted: {MUTED};
            --paper: {PAPER};
            --panel: {PANEL};
            --border: {BORDER};
            --clay: {CLAY};
        }}

        html, body, [data-testid="stAppViewContainer"] {{
            background: linear-gradient(180deg, #f7f1e8 0%, #f2e8db 100%);
            color: var(--ink);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}

        [data-testid="stHeader"], [data-testid="stToolbar"] {{
            background: transparent;
        }}

        [data-testid="block-container"] {{
            max-width: 1240px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }}

        h1, h2, h3 {{
            color: var(--ink);
            letter-spacing: 0;
        }}

        h1 {{
            font-size: clamp(3.1rem, 7vw, 6.3rem) !important;
            line-height: 0.94 !important;
            font-weight: 650 !important;
            margin-bottom: 1rem !important;
        }}

        h2 {{
            font-size: 1.95rem !important;
            line-height: 1.08 !important;
            margin-top: 2.6rem !important;
            border-top: 1px solid var(--border);
            padding-top: 1.15rem;
        }}

        h3 {{
            font-size: 1rem !important;
            font-weight: 650 !important;
        }}

        .stMarkdown p, .stCaptionContainer {{
            color: var(--muted);
        }}

        div[data-testid="stMetric"] {{
            background: var(--panel);
            border: 1px solid var(--border);
            min-height: 124px;
            padding: 0.95rem 1rem 0.8rem;
        }}

        div[data-testid="stMetric"] label p {{
            color: var(--muted);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 650;
        }}

        div[data-testid="stMetricValue"] {{
            color: var(--ink);
            font-weight: 650;
            font-size: 1.78rem;
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid var(--border);
            background: var(--panel);
        }}

        .stButton button {{
            background: var(--ink);
            color: var(--paper);
            border: 1px solid var(--ink);
            border-radius: 0;
            padding: 0.55rem 0.9rem;
            font-weight: 650;
        }}

        .stButton button:hover {{
            border-color: var(--clay);
            color: var(--paper);
            background: #2b2927;
        }}

        .stMultiSelect [data-baseweb="select"] > div,
        .stSelectbox [data-baseweb="select"] > div,
        .stSlider [data-baseweb="slider"] {{
            background: var(--panel);
            border-color: var(--border);
        }}

        [data-testid="stWidgetLabel"] p,
        [data-testid="stCheckbox"] label p {{
            color: var(--ink);
            font-weight: 650;
        }}

        .hero {{
            display: grid;
            grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.72fr);
            gap: 2.2rem;
            align-items: end;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.9rem;
            margin-bottom: 1.2rem;
        }}

        .eyebrow {{
            color: var(--clay);
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-weight: 700;
            margin-bottom: 1rem;
        }}

        .lede {{
            max-width: 780px;
            color: var(--ink);
            font-size: 1.13rem;
            line-height: 1.55;
        }}

        .disclaimer {{
            display: inline-flex;
            margin-top: 1.15rem;
            border: 1px solid rgba(196, 95, 60, 0.35);
            background: rgba(196, 95, 60, 0.08);
            color: #7e321d;
            padding: 0.68rem 0.8rem;
            font-size: 0.9rem;
            font-weight: 600;
        }}

        .side-panel {{
            background: var(--ink);
            color: var(--paper);
            border: 1px solid var(--ink);
            padding: 1.1rem;
        }}

        .side-panel p {{
            margin: 0;
            color: rgba(247, 241, 232, 0.78);
            font-size: 0.86rem;
            line-height: 1.45;
        }}

        .side-panel strong {{
            display: block;
            color: var(--paper);
            font-size: 1rem;
            margin-bottom: 0.7rem;
        }}

        .pipeline-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }}

        .pill {{
            border: 1px solid rgba(247, 241, 232, 0.28);
            color: var(--paper);
            padding: 0.32rem 0.52rem;
            font-size: 0.78rem;
        }}

        .section-kicker {{
            color: var(--clay);
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.76rem;
            font-weight: 700;
            margin-top: 2.4rem;
        }}

        .note-band {{
            border-left: 3px solid var(--clay);
            background: rgba(251, 247, 239, 0.78);
            padding: 0.9rem 1rem;
            color: var(--muted);
            font-size: 0.95rem;
            line-height: 1.55;
            margin: 0.8rem 0 1.15rem;
        }}

        .control-panel {{
            border: 1px solid var(--border);
            background: rgba(251, 247, 239, 0.84);
            padding: 1rem;
            margin: 0.5rem 0 1.2rem;
        }}

        .control-help {{
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.45;
            margin: -0.2rem 0 0.65rem;
        }}

        .report-extract {{
            border: 1px solid var(--border);
            background: var(--panel);
            padding: 1rem;
            margin: 0.4rem 0 1.2rem;
        }}

        .chart-card {{
            border: 1px solid var(--border);
            background: var(--panel);
            padding: 0.85rem;
            margin-bottom: 1rem;
        }}

        .chart-title {{
            color: var(--ink);
            font-size: 0.86rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}

        .chart-note {{
            color: var(--muted);
            font-size: 0.78rem;
            margin-bottom: 0.55rem;
        }}

        .script-box {{
            background: var(--ink);
            color: var(--paper);
            padding: 1.35rem;
            margin-top: 0.5rem;
        }}

        .script-box h4 {{
            color: var(--paper);
            margin: 0 0 0.65rem;
            font-size: 1.05rem;
        }}

        .script-box p {{
            color: rgba(247, 241, 232, 0.82);
            line-height: 1.55;
        }}

        .quality-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 0.75rem;
            margin-bottom: 1rem;
        }}

        .quality-card {{
            border: 1px solid var(--border);
            background: var(--panel);
            padding: 0.9rem;
        }}

        .quality-card .number {{
            font-size: 2rem;
            line-height: 1;
            color: var(--ink);
            font-weight: 650;
        }}

        .quality-card .label {{
            margin-top: 0.45rem;
            color: var(--muted);
            font-size: 0.82rem;
        }}

        @media (max-width: 850px) {{
            .hero {{
                grid-template-columns: 1fr;
                gap: 1.2rem;
            }}
            [data-testid="block-container"] {{
                padding-left: 1rem;
                padding-right: 1rem;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(metrics: dict[str, object]) -> None:
    st.markdown(
        f"""
        <div class="hero">
            <div>
                <div class="eyebrow">Personal / academic demo</div>
                <h1>Risk Reporting<br>& BI Demo</h1>
                <div class="lede">
                    Demo educativa de reporting de riesgo sobre datos transaccionales.
                    El objetivo es transformar datos en KPIs, alertas y visualizaciones utiles
                    para priorizar revision.
                </div>
                <div class="disclaimer">
                    Proyecto personal / academico. No representa un sistema bancario real ni un modelo regulatorio.
                </div>
            </div>
            <div class="side-panel">
                <strong>Demo flow</strong>
                <p>
                    CSV ficticio, limpieza con Pandas, reglas explicables, KPIs de reporting
                    y tabla de alertas con reason codes de negocio.
                </p>
                <div class="pipeline-row">
                    <span class="pill">Raw CSV</span>
                    <span class="pill">Data quality</span>
                    <span class="pill">Rules</span>
                    <span class="pill">KPIs</span>
                    <span class="pill">Review</span>
                </div>
                <p style="margin-top:1rem;">
                    {metrics["total_transactions"]} clean transactions · {metrics["total_alerts"]} alerts ·
                    {metrics["data_quality_issues_detected"]} raw data issues
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(kicker: str, title: str, body: str | None = None) -> None:
    st.markdown(f'<div class="section-kicker">{kicker}</div>', unsafe_allow_html=True)
    st.header(title)
    if body:
        st.markdown(f'<div class="note-band">{body}</div>', unsafe_allow_html=True)


def chart_shell(title: str, note: str) -> None:
    st.markdown(
        f'<div class="chart-title">{title}</div><div class="chart-note">{note}</div>',
        unsafe_allow_html=True,
    )


def chart_base(chart: alt.Chart | alt.LayerChart) -> alt.Chart | alt.LayerChart:
    return (
        chart.configure(background=PANEL)
        .configure_view(stroke=None, fill=PANEL)
        .configure_axis(
            labelColor=MUTED,
            titleColor=MUTED,
            domainColor=BORDER,
            tickColor=BORDER,
            gridColor=GRID,
            labelFont="Inter",
            titleFont="Inter",
            labelFontSize=11,
            titleFontSize=11,
        )
        .configure_legend(labelColor=MUTED, titleColor=MUTED, labelFont="Inter", titleFont="Inter")
    )


def empty_chart(message: str = "No data for current filters") -> alt.Chart:
    data = pd.DataFrame({"message": [message]})
    return chart_base(
        alt.Chart(data)
        .mark_text(color=MUTED, fontSize=14)
        .encode(text="message:N")
        .properties(height=240)
    )


def severity_chart(alerts: pd.DataFrame) -> alt.Chart | alt.LayerChart:
    order = pd.DataFrame({"severity": ["LOW", "MEDIUM", "HIGH"]})
    counts = alerts.groupby("severity", as_index=False).size().rename(columns={"size": "alerts"})
    data = order.merge(counts, on="severity", how="left").fillna({"alerts": 0})
    if data["alerts"].sum() == 0:
        return empty_chart()
    ymax = max(int(data["alerts"].max()) + 1, 1)
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("severity:N", sort=["LOW", "MEDIUM", "HIGH"], title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("alerts:Q", title="Alerts", scale=alt.Scale(domain=[0, ymax])),
            color=alt.Color(
                "severity:N",
                scale=alt.Scale(domain=["LOW", "MEDIUM", "HIGH"], range=[GREEN, GOLD, ROSE]),
                legend=None,
            ),
            tooltip=["severity:N", "alerts:Q"],
        )
        .properties(height=260)
    )
    labels = chart.mark_text(dy=-8, color=INK, fontSize=13, fontWeight="bold").encode(text="alerts:Q")
    return chart_base(chart + labels)


def rule_chart(alerts: pd.DataFrame) -> alt.Chart | alt.LayerChart:
    data = alerts.groupby("rule_triggered", as_index=False).size().rename(columns={"size": "alerts"})
    if data.empty:
        return empty_chart()
    xmax = max(int(data["alerts"].max()) + 1, 1)
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3, color=CLAY)
        .encode(
            y=alt.Y("rule_triggered:N", sort="-x", title=None, axis=alt.Axis(labelLimit=180)),
            x=alt.X("alerts:Q", title="Alerts", scale=alt.Scale(domain=[0, xmax])),
            tooltip=["rule_triggered:N", "alerts:Q"],
        )
        .properties(height=260)
    )
    labels = chart.mark_text(align="left", dx=6, color=INK, fontSize=12).encode(text="alerts:Q")
    return chart_base(chart + labels)


def amount_time_chart(alerts: pd.DataFrame) -> alt.Chart | alt.LayerChart:
    if alerts.empty:
        return empty_chart()
    data = (
        alerts.groupby("detection_date", as_index=False)
        .agg(total_alert_amount=("alert_amount", "sum"), alerts=("alert_id", "count"))
        .sort_values("detection_date")
    )
    data["detection_date"] = pd.to_datetime(data["detection_date"])
    base = alt.Chart(data).encode(
        x=alt.X("detection_date:T", title=None, axis=alt.Axis(format="%d %b", grid=False)),
        y=alt.Y("total_alert_amount:Q", title="Amount under alert"),
        tooltip=[
            alt.Tooltip("detection_date:T", title="Date"),
            alt.Tooltip("total_alert_amount:Q", title="Amount", format=",.2f"),
            alt.Tooltip("alerts:Q", title="Alerts"),
        ],
    )
    chart = (
        base.mark_area(color=CLAY, opacity=0.16)
        + base.mark_line(color=INK, strokeWidth=2.2)
        + base.mark_point(color=CLAY, filled=True, size=70)
    ).properties(height=260)
    return chart_base(chart)


def top_accounts_chart(alerts: pd.DataFrame) -> alt.Chart | alt.LayerChart:
    data = (
        alerts.groupby("account_id", as_index=False)["alert_amount"]
        .sum()
        .sort_values("alert_amount", ascending=False)
        .head(8)
    )
    if data.empty:
        return empty_chart()
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3, color=INK)
        .encode(
            y=alt.Y("account_id:N", sort="-x", title=None, axis=alt.Axis(labelLimit=160)),
            x=alt.X("alert_amount:Q", title="Amount under alert"),
            tooltip=["account_id:N", alt.Tooltip("alert_amount:Q", format=",.2f")],
        )
        .properties(height=260)
    )
    return chart_base(chart)


def credit_bucket_chart(credit_table: pd.DataFrame) -> alt.Chart | alt.LayerChart:
    bucket_order = ["CURRENT", "1-30 DPD", "31-60 DPD", "61-90 DPD", "90+ DPD"]
    counts = (
        credit_table.groupby("delinquency_bucket", as_index=False)
        .size()
        .rename(columns={"size": "loans"})
    )
    data = pd.DataFrame({"delinquency_bucket": bucket_order}).merge(counts, how="left").fillna({"loans": 0})
    if data["loans"].sum() == 0:
        return empty_chart("No loan data available")
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, color=CLAY)
        .encode(
            x=alt.X(
                "delinquency_bucket:N",
                sort=bucket_order,
                title=None,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("loans:Q", title="Loans"),
            tooltip=["delinquency_bucket:N", "loans:Q"],
        )
        .properties(height=260)
    )
    labels = chart.mark_text(dy=-8, color=INK, fontSize=12, fontWeight="bold").encode(text="loans:Q")
    return chart_base(chart + labels)


def expected_loss_by_product_chart(credit_table: pd.DataFrame) -> alt.Chart | alt.LayerChart:
    data = (
        credit_table.groupby("product_type", as_index=False)["expected_loss"]
        .sum()
        .sort_values("expected_loss", ascending=False)
    )
    if data.empty:
        return empty_chart("No expected loss data available")
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3, color=INK)
        .encode(
            y=alt.Y("product_type:N", sort="-x", title=None, axis=alt.Axis(labelLimit=160)),
            x=alt.X("expected_loss:Q", title="Expected Loss"),
            tooltip=["product_type:N", alt.Tooltip("expected_loss:Q", format=",.2f")],
        )
        .properties(height=260)
    )
    return chart_base(chart)


def quality_cards(dq_summary: pd.DataFrame) -> None:
    cards = []
    for _, row in dq_summary.iterrows():
        cards.append(
            f"""
            <div class="quality-card">
                <div class="number">{int(row["issues"])}</div>
                <div class="label">{row["check"]}</div>
            </div>
            """
        )
    st.markdown(f'<div class="quality-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def run_refresh_animation() -> None:
    with st.status("Refreshing reporting layer", expanded=True) as status:
        progress = st.progress(0)
        steps = [
            ("Loading cleaned transactions", 20),
            ("Applying alert filters", 45),
            ("Recalculating KPIs", 70),
            ("Rendering review workspace", 100),
        ]
        for label, value in steps:
            st.write(label)
            progress.progress(value)
            time.sleep(0.22)
        status.update(label="Reporting layer refreshed", state="complete", expanded=False)


def checkbox_filter(label: str, options: list[str], key: str, columns: int = 2) -> list[str]:
    st.markdown(f"**{label}**")
    st.markdown(
        '<div class="control-help">Marca y desmarca opciones libremente. Siempre puedes recuperarlas.</div>',
        unsafe_allow_html=True,
    )

    button_col1, button_col2 = st.columns(2)
    with button_col1:
        if st.button("Select all", key=f"{key}_select_all", use_container_width=True):
            for option in options:
                st.session_state[f"{key}_{option}"] = True
    with button_col2:
        if st.button("Clear", key=f"{key}_clear", use_container_width=True):
            for option in options:
                st.session_state[f"{key}_{option}"] = False

    selected: list[str] = []
    cols = st.columns(max(1, min(columns, len(options))))
    for index, option in enumerate(options):
        option_key = f"{key}_{option}"
        if option_key not in st.session_state:
            st.session_state[option_key] = True
        with cols[index % len(cols)]:
            if st.checkbox(option, key=option_key):
                selected.append(option)
    return selected


def show_report_extract(
    filtered_alerts: pd.DataFrame,
    filtered_review: pd.DataFrame,
    date_range: tuple[pd.Timestamp, pd.Timestamp],
) -> None:
    st.subheader("Latest report refresh output")

    if filtered_alerts.empty:
        st.warning("The refresh completed, but the current filters return no alerts.")
        return

    top_rule = filtered_alerts["rule_triggered"].value_counts().idxmax()
    top_account_row = (
        filtered_alerts.groupby("account_id", as_index=False)["alert_amount"]
        .sum()
        .sort_values("alert_amount", ascending=False)
        .iloc[0]
    )
    summary = pd.DataFrame(
        [
            {"report_item": "Detection period", "value": f"{date_range[0]} to {date_range[1]}"},
            {"report_item": "Alert records", "value": f"{len(filtered_alerts)}"},
            {"report_item": "Review transactions", "value": f"{len(filtered_review)}"},
            {"report_item": "Total amount under alert", "value": money(float(filtered_alerts["alert_amount"].sum()))},
            {"report_item": "Most common rule", "value": top_rule},
            {
                "report_item": "Highest exposure account",
                "value": f"{top_account_row['account_id']} ({money(float(top_account_row['alert_amount']))})",
            },
        ]
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.caption("Report extract generated from the active filters.")
    st.dataframe(
        filtered_alerts[
            [
                "alert_id",
                "account_id",
                "detection_date",
                "rule_triggered",
                "severity",
                "reason_code",
                "alert_amount",
                "status",
            ]
        ].sort_values(["severity", "rule_triggered", "account_id"]),
        use_container_width=True,
        hide_index=True,
        column_config={"alert_amount": st.column_config.NumberColumn("alert_amount", format="EUR %.2f")},
    )


def filtered_alerts_and_review(
    alerts: pd.DataFrame,
    review_table: pd.DataFrame,
    severities: list[str],
    rules: list[str],
    accounts: list[str],
    min_amount: float,
    date_range: tuple[pd.Timestamp, pd.Timestamp],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    alerts = alerts.copy()
    review = review_table.copy()
    start_date, end_date = date_range

    alerts["detection_date_dt"] = pd.to_datetime(alerts["detection_date"]).dt.date
    alerts = alerts[
        alerts["severity"].isin(severities)
        & alerts["rule_triggered"].isin(rules)
        & alerts["account_id"].isin(accounts)
        & (alerts["alert_amount"] >= min_amount)
        & (alerts["detection_date_dt"] >= start_date)
        & (alerts["detection_date_dt"] <= end_date)
    ]

    review = review[
        review["severity"].isin(severities)
        & review["rule_triggered"].isin(rules)
        & review["account_id"].isin(accounts)
        & (pd.to_datetime(review["date"]).dt.date >= start_date)
        & (pd.to_datetime(review["date"]).dt.date <= end_date)
    ]
    return alerts.drop(columns=["detection_date_dt"]), review


try:
    data = load_dashboard_data()
except FileNotFoundError:
    inject_css()
    st.title("Risk Reporting & BI Demo")
    st.warning("Run the Python pipeline before opening the dashboard.")
    st.code(
        "python src/ingest_data.py\n"
        "python src/clean_data.py\n"
        "python src/generate_features.py\n"
        "python src/detect_alerts.py\n"
        "python src/credit_risk_metrics.py\n"
        "streamlit run app.py",
        language="bash",
    )
    st.stop()


inject_css()

metrics = data["metrics"]
alerts = data["alerts"].copy()
review_table = data["review_table"].copy()
alerts["alert_amount"] = pd.to_numeric(alerts["metric_2_value"], errors="coerce").fillna(0)

hero(metrics)

section(
    "01 / Controls",
    "Interactive Reporting Workspace",
    "Usa los filtros y el boton de refresh para simular una mini ejecucion de reporting. La vista recalcula KPIs, graficas y tabla de revision.",
)

all_severities = sorted(alerts["severity"].unique())
all_rules = sorted(alerts["rule_triggered"].unique())
all_accounts = sorted(alerts["account_id"].unique())
all_dates = pd.to_datetime(alerts["detection_date"]).dt.date

filter_left, filter_mid, filter_right = st.columns([0.9, 1.2, 1])
with filter_left:
    severity_filter = checkbox_filter("Severity", all_severities, "severity_filter", columns=1)
with filter_mid:
    rule_filter = checkbox_filter("Rule / typology", all_rules, "rule_filter", columns=1)
with filter_right:
    account_choice = st.selectbox("Focus account", ["All accounts"] + all_accounts)
    account_filter = all_accounts if account_choice == "All accounts" else [account_choice]
    min_amount = st.slider(
        "Minimum alert amount",
        min_value=0,
        max_value=int(alerts["alert_amount"].max()),
        value=0,
        step=1_000,
    )

control_bottom1, control_bottom2 = st.columns([1.25, 0.75])
with control_bottom1:
    selected_dates = st.date_input(
        "Detection date range",
        value=(all_dates.min(), all_dates.max()),
        min_value=all_dates.min(),
        max_value=all_dates.max(),
    )
with control_bottom2:
    st.markdown("&nbsp;", unsafe_allow_html=True)
    run_clicked = st.button("Run report refresh", use_container_width=True)
    if run_clicked:
        run_refresh_animation()
        st.session_state["report_has_run"] = True
        st.session_state["report_run_number"] = st.session_state.get("report_run_number", 0) + 1
        st.session_state["report_run_time"] = pd.Timestamp.now().strftime("%H:%M:%S")

if len(selected_dates) == 2:
    date_range = selected_dates
else:
    date_range = (all_dates.min(), all_dates.max())

filtered_alerts, filtered_review = filtered_alerts_and_review(
    alerts,
    review_table,
    severity_filter,
    rule_filter,
    account_filter,
    float(min_amount),
    date_range,
)

filtered_total_alerts = int(len(filtered_alerts))
filtered_amount = float(filtered_alerts["alert_amount"].sum())
filtered_avg = filtered_amount / filtered_total_alerts if filtered_total_alerts else 0
filtered_alert_rate = filtered_total_alerts / metrics["total_transactions"] if metrics["total_transactions"] else 0

if st.session_state.get("report_has_run"):
    st.caption(
        f"Last refresh #{st.session_state.get('report_run_number', 1)} "
        f"completed at {st.session_state.get('report_run_time', 'now')}."
    )
    show_report_extract(filtered_alerts, filtered_review, date_range)

section("02 / Summary", "KPI Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total transactions", f"{metrics['total_transactions']:,}")
col2.metric("Filtered alerts", f"{filtered_total_alerts:,}", delta=f"{filtered_total_alerts - metrics['total_alerts']:+d} vs all")
col3.metric("Filtered alert rate", pct(filtered_alert_rate))
col4.metric("Filtered amount under alert", money(filtered_amount))

col5, col6, col7 = st.columns(3)
col5.metric("Average alert amount", money(filtered_avg))
col6.metric("Accounts in current view", f"{filtered_alerts['account_id'].nunique():,}")
col7.metric("Data quality issues detected", f"{metrics['data_quality_issues_detected']:,}")

section(
    "03 / Monitoring",
    "Risk / Alert Monitoring",
    "Graficas recalculadas con los filtros activos. La idea es poder explicar volumen, tipologia, importe y foco de revision.",
)
left, right = st.columns(2)
with left:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_shell("Alerts by severity", "Cuantas alertas quedan por nivel de severidad.")
    st.altair_chart(severity_chart(filtered_alerts), use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_shell("Alerts by rule / typology", "Distribucion por regla explicable.")
    st.altair_chart(rule_chart(filtered_alerts), use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

left, right = st.columns(2)
with left:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_shell("Alert amount over time", "Importe bajo alerta por fecha de deteccion.")
    st.altair_chart(amount_time_chart(filtered_alerts), use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_shell("Top customers/accounts by alert amount", "Cuentas que concentran mayor importe bajo alerta.")
    st.altair_chart(top_accounts_chart(filtered_alerts), use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

section(
    "04 / Review",
    "Alert Review Workspace",
    "Selecciona una alerta y revisa reason code, ventana, importe y transacciones de soporte.",
)

if filtered_alerts.empty:
    st.warning("No alerts match the current filters. Reduce the amount threshold or include more severities/rules.")
else:
    alert_options = (
        filtered_alerts.assign(
            option=lambda frame: frame["alert_id"]
            + " | "
            + frame["account_id"]
            + " | "
            + frame["rule_triggered"]
            + " | "
            + frame["reason_code"]
        )
        .sort_values(["severity", "rule_triggered", "account_id"])
    )
    selected_option = st.selectbox("Alert to review", alert_options["option"].tolist())
    selected_alert_id = selected_option.split(" | ")[0]
    selected_alert = filtered_alerts[filtered_alerts["alert_id"] == selected_alert_id].iloc[0]
    selected_transactions = filtered_review[
        (filtered_review["account_id"] == selected_alert["account_id"])
        & (filtered_review["rule_triggered"] == selected_alert["rule_triggered"])
    ]

    detail1, detail2, detail3, detail4 = st.columns(4)
    detail1.metric("Account", selected_alert["account_id"])
    detail2.metric("Rule", selected_alert["rule_triggered"])
    detail3.metric("Severity", selected_alert["severity"])
    detail4.metric("Amount", money(float(selected_alert["alert_amount"])))

    st.markdown(
        f"""
        <div class="note-band">
            <strong>Reason code:</strong> {selected_alert["reason_code"]}<br>
            <strong>Business explanation:</strong> {selected_alert["reason"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.dataframe(
        selected_transactions,
        use_container_width=True,
        hide_index=True,
        column_config={"amount": st.column_config.NumberColumn("amount", format="EUR %.2f")},
    )

with st.expander("Full filtered alert table", expanded=False):
    st.dataframe(
        filtered_review,
        use_container_width=True,
        hide_index=True,
        column_config={"amount": st.column_config.NumberColumn("amount", format="EUR %.2f")},
    )

with st.expander("Reason code guide", expanded=True):
    reason_codes = (
        alerts[["rule_triggered", "reason_code"]]
        .drop_duplicates()
        .sort_values("rule_triggered")
        .reset_index(drop=True)
    )
    st.dataframe(reason_codes, use_container_width=True, hide_index=True)

section(
    "05 / Quality",
    "Data Quality",
    "Checks basicos sobre el fichero raw antes de confiar en las metricas del dashboard.",
)
quality_cards(metrics["data_quality_summary"])
st.dataframe(metrics["data_quality_summary"], use_container_width=True, hide_index=True)

section(
    "06 / Credit Risk",
    "Credit Risk Reporting",
    "Mini capa educativa de riesgo de credito para entrevista. Extiende el proyecto AML con una cartera sintetica y conceptos basicos: morosidad 30/60/90, NPL >90 DPD, PD, EAD, LGD, Expected Loss, recovery rate, stress simple y calidad de datos.",
)

stress_multiplier = st.slider(
    "Stress multiplier",
    min_value=1.0,
    max_value=2.0,
    value=1.5,
    step=0.1,
    help="Multiplica la PD para simular un deterioro simple de cartera. La PD estresada queda limitada a 1.",
)
credit_table = load_credit_risk_table(stress_multiplier=stress_multiplier)
credit_raw = pd.read_csv(RAW_DIR / "loans.csv")
credit_dq_summary = credit_data_quality_summary(credit_raw)
credit_metrics = calculate_credit_risk_metrics(credit_table, credit_dq_summary)

credit_col1, credit_col2, credit_col3, credit_col4 = st.columns(4)
credit_col1.metric("Total loans", f"{credit_metrics['total_loans']:,}")
credit_col2.metric("NPL rate", pct(credit_metrics["npl_rate"]))
credit_col3.metric("Early warning loans", f"{credit_metrics['early_warning_count']:,}")
credit_col4.metric("Total EAD", money(credit_metrics["total_ead"]))

credit_col5, credit_col6, credit_col7 = st.columns(3)
credit_col5.metric("Expected Loss", money(credit_metrics["expected_loss"]))
credit_col6.metric("Stressed Expected Loss", money(credit_metrics["stressed_expected_loss"]))
credit_col7.metric("Average Recovery Rate", pct(credit_metrics["average_recovery_rate"]))

left, right = st.columns(2)
with left:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_shell("Loans by delinquency bucket", "Distribucion de morosidad: current, 30, 60, 90 y NPL.")
    st.altair_chart(credit_bucket_chart(credit_table), use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_shell("Expected Loss by product type", "PD x EAD x LGD agregado por producto.")
    st.altair_chart(expected_loss_by_product_chart(credit_table), use_container_width=True, theme=None)
    st.markdown("</div>", unsafe_allow_html=True)

st.subheader("Credit risk loan table")
st.dataframe(
    credit_table[
        [
            "loan_id",
            "customer_id",
            "product_type",
            "days_past_due",
            "delinquency_bucket",
            "pd",
            "ead",
            "lgd",
            "expected_loss",
            "npl_flag",
            "early_warning_flag",
        ]
    ],
    use_container_width=True,
    hide_index=True,
    column_config={
        "pd": st.column_config.NumberColumn("pd", format="%.2%"),
        "ead": st.column_config.NumberColumn("ead", format="EUR %.2f"),
        "lgd": st.column_config.NumberColumn("lgd", format="%.2%"),
        "expected_loss": st.column_config.NumberColumn("expected_loss", format="EUR %.2f"),
    },
)

with st.expander("Stress recalculation detail", expanded=False):
    st.dataframe(
        credit_table[
            [
                "loan_id",
                "pd",
                "stressed_pd",
                "ead",
                "lgd",
                "expected_loss",
                "stressed_expected_loss",
            ]
        ].sort_values("stressed_expected_loss", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "pd": st.column_config.NumberColumn("pd", format="%.2%"),
            "stressed_pd": st.column_config.NumberColumn("stressed_pd", format="%.2%"),
            "ead": st.column_config.NumberColumn("ead", format="EUR %.2f"),
            "lgd": st.column_config.NumberColumn("lgd", format="%.2%"),
            "expected_loss": st.column_config.NumberColumn("expected_loss", format="EUR %.2f"),
            "stressed_expected_loss": st.column_config.NumberColumn("stressed_expected_loss", format="EUR %.2f"),
        },
    )

st.subheader("Credit data quality")
quality_cards(credit_dq_summary)
st.dataframe(credit_dq_summary, use_container_width=True, hide_index=True)

section("07 / Interview Mode", "How to explain this demo")
st.markdown(
    """
    <div class="script-box">
        <h4>Guion breve en espanol</h4>
        <p>
            Este proyecto resuelve un problema sencillo de reporting de riesgo: convertir transacciones
            sinteticas en una vista clara de KPIs, alertas y calidad de dato. El pipeline carga CSVs,
            normaliza campos, limpia registros con problemas, genera features basicas por cuenta y aplica
            reglas explicables para crear alertas.
        </p>
        <p>
            Los controles permiten simular una revision BI: filtrar por severidad, regla, cuenta, fecha e
            importe minimo. La vista recalcula KPIs, graficas y tabla de revision, y el inspector permite
            defender una alerta concreta con reason code y evidencia transaccional.
        </p>
        <p>
            La limitacion principal es que es un prototipo junior con datos ficticios y reglas fijas. No es
            un modelo regulatorio, no toma decisiones reales y siempre requeriria revision humana y mas
            contexto de negocio.
        </p>
        <p>
            La capa de credito complementa la demo AML: permite explicar NPL, PD, EAD, LGD, Expected Loss,
            tasas de recuperacion y un stress test simple sin mezclar esos conceptos con
            deteccion de blanqueo.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
