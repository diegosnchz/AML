from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from sqlalchemy import create_engine, text


LOGGER = logging.getLogger("amlguardian.airflow")
PROJECT_DIR = "/opt/amlguardian"
DBT_DIR = f"{PROJECT_DIR}/dbt"


def postgres_url() -> str:
    return (
        "postgresql+psycopg2://"
        f"{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@postgres:5432/{os.environ['POSTGRES_DB']}"
    )


def notify_completion() -> None:
    engine = create_engine(postgres_url(), future=True)
    queries = {
        "raw_transactions": "select count(*) from raw.transactions",
        "feature_accounts": "select count(*) from features.fct_account_features",
        "alerts": "select count(*) from alerts.fct_alerts",
        "sar_candidates": "select count(*) from alerts.fct_sar_candidates",
        "risk_scores": "select count(*) from ml.risk_scores",
        "graph_metrics": "select count(*) from ml.graph_account_metrics",
    }

    summary = {}
    with engine.connect() as connection:
        for label, query in queries.items():
            summary[label] = connection.execute(text(query)).scalar_one()

    LOGGER.info("AMLGuardian pipeline completed successfully")
    LOGGER.info("Pipeline summary: %s", summary)


default_args = {
    "owner": "amlguardian",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="amlguardian_pipeline",
    description="End-to-end AMLGuardian monitoring pipeline: ingestion, dbt, graph analytics, and ML scoring.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="Europe/Madrid"),
    schedule="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["aml", "fincrime", "portfolio"],
) as dag:
    common_env = {
        **os.environ,
        "DBT_PROFILES_DIR": DBT_DIR,
        "PYTHONPATH": f"/opt/airflow:{PROJECT_DIR}",
    }

    ingest_raw_data = BashOperator(
        task_id="ingest_raw_data",
        env=common_env,
        bash_command=f"python {PROJECT_DIR}/scripts/ingest.py",
    )

    run_dbt_staging = BashOperator(
        task_id="run_dbt_staging",
        env=common_env,
        bash_command=f"dbt run --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} --select staging",
    )

    run_dbt_features = BashOperator(
        task_id="run_dbt_features",
        env=common_env,
        bash_command=f"dbt run --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} --select marts.features",
    )

    run_dbt_alerts = BashOperator(
        task_id="run_dbt_alerts",
        env=common_env,
        bash_command=f"dbt run --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} --select marts.alerts",
    )

    run_dbt_tests = BashOperator(
        task_id="run_dbt_tests",
        env=common_env,
        bash_command=(
            f"dbt test --project-dir {DBT_DIR} --profiles-dir {DBT_DIR} "
            f"&& dbt docs generate --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}"
        ),
    )

    load_neo4j_graph = BashOperator(
        task_id="load_neo4j_graph",
        env=common_env,
        bash_command=f"python {PROJECT_DIR}/scripts/load_graph.py",
    )

    train_ml_model = BashOperator(
        task_id="train_ml_model",
        env=common_env,
        bash_command=f"python {PROJECT_DIR}/scripts/train_model.py",
    )

    notify_completion_task = PythonOperator(
        task_id="notify_completion",
        python_callable=notify_completion,
    )

    (
        ingest_raw_data
        >> run_dbt_staging
        >> run_dbt_features
        >> run_dbt_alerts
        >> run_dbt_tests
        >> load_neo4j_graph
        >> train_ml_model
        >> notify_completion_task
    )

