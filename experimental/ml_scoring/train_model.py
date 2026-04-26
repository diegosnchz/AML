from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import shap
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sqlalchemy import text
from xgboost import XGBClassifier

sys.path.append(str(Path(__file__).resolve().parents[1] / "orchestration" / "legacy_postgres_ingestion"))

from common import configure_logging, env, ensure_directory, get_engine


LOGGER = configure_logging("amlguardian.ml")
RANDOM_STATE = 42


def load_feature_dataset() -> pd.DataFrame:
    engine = get_engine()
    dataset = pd.read_sql(
        """
        SELECT *
        FROM features.fct_account_features
        ORDER BY account_id
        """,
        engine,
    )
    LOGGER.info("Loaded %s feature rows from Postgres", len(dataset))
    return dataset


def build_supervised_models() -> dict[str, Pipeline]:
    return {
        "xgboost": Pipeline(
            steps=[
                ("smote", SMOTE(random_state=RANDOM_STATE)),
                (
                    "model",
                    XGBClassifier(
                        objective="binary:logistic",
                        eval_metric="logloss",
                        n_estimators=300,
                        learning_rate=0.05,
                        max_depth=5,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        min_child_weight=2,
                        reg_lambda=1.0,
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "lightgbm": Pipeline(
            steps=[
                ("smote", SMOTE(random_state=RANDOM_STATE)),
                (
                    "model",
                    LGBMClassifier(
                        n_estimators=300,
                        learning_rate=0.05,
                        num_leaves=31,
                        subsample=0.85,
                        colsample_bytree=0.85,
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }


def evaluate_supervised_model(model: Pipeline, x_train, x_test, y_train, y_test) -> dict:
    model.fit(x_train, y_train)
    probabilities = model.predict_proba(x_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    return {
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "probabilities": probabilities,
        "predictions": predictions,
        "estimator": model,
    }


def evaluate_isolation_forest(x_train, x_test, y_test, contamination: float) -> dict:
    model = IsolationForest(
        n_estimators=300,
        contamination=max(contamination, 0.001),
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(x_train)
    anomaly_score = -model.decision_function(x_test)
    scaled_score = (anomaly_score - anomaly_score.min()) / (
        (anomaly_score.max() - anomaly_score.min()) or 1.0
    )
    predictions = (model.predict(x_test) == -1).astype(int)
    return {
        "pr_auc": float(average_precision_score(y_test, scaled_score)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "probabilities": scaled_score,
        "predictions": predictions,
        "estimator": model,
    }


def generate_shap_outputs(model: Pipeline, features: pd.DataFrame, output_dir: Path) -> list[str]:
    classifier = model.named_steps["model"]
    explainer = shap.TreeExplainer(classifier)
    shap_values = explainer.shap_values(features)

    summary_sample = features.sample(min(len(features), 10_000), random_state=RANDOM_STATE)
    shap_sample = explainer.shap_values(summary_sample)
    plt.figure(figsize=(12, 7))
    shap.summary_plot(shap_sample, summary_sample, show=False)
    plt.tight_layout()
    shap_path = output_dir / "shap_summary.png"
    plt.savefig(shap_path, dpi=180, bbox_inches="tight")
    plt.close()
    LOGGER.info("Saved SHAP summary plot to %s", shap_path)

    top_features = []
    for row_values in shap_values:
        contributions = (
            pd.Series(row_values, index=features.columns)
            .abs()
            .sort_values(ascending=False)
            .head(3)
            .index.tolist()
        )
        top_features.append("|".join(contributions))
    return top_features


def assign_risk_tier(score: float) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def persist_results(predictions: pd.DataFrame, metrics: dict, output_dir: Path) -> None:
    engine = get_engine()
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "risk_scores.csv"
    predictions[["account_id", "risk_score", "risk_tier", "top_3_features"]].to_csv(
        csv_path,
        index=False,
    )
    LOGGER.info("Saved risk scores to %s", csv_path)

    metrics_path = output_dir / "model_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    LOGGER.info("Saved model benchmark metrics to %s", metrics_path)

    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS ml"))
        connection.execute(text("DROP TABLE IF EXISTS ml.risk_scores"))
    predictions.to_sql(
        "risk_scores",
        engine,
        schema="ml",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5_000,
    )


def main() -> None:
    output_dir = ensure_directory(env("OUTPUT_DIR", "outputs"))
    dataset = load_feature_dataset().fillna(0)

    target = dataset["is_laundering_any"].astype(int)
    features = dataset.drop(columns=["account_id", "is_laundering_any"])

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.25,
        random_state=RANDOM_STATE,
        stratify=target,
    )

    contamination = float(y_train.mean())
    benchmark_results: dict[str, dict] = {}
    supervised_models = build_supervised_models()

    for model_name, model in supervised_models.items():
        LOGGER.info("Training %s benchmark", model_name)
        evaluation = evaluate_supervised_model(model, x_train, x_test, y_train, y_test)
        benchmark_results[model_name] = {
            "pr_auc": evaluation["pr_auc"],
            "f1": evaluation["f1"],
            "confusion_matrix": evaluation["confusion_matrix"],
        }

    LOGGER.info("Training isolation_forest benchmark")
    isolation_evaluation = evaluate_isolation_forest(x_train, x_test, y_test, contamination)
    benchmark_results["isolation_forest"] = {
        "pr_auc": isolation_evaluation["pr_auc"],
        "f1": isolation_evaluation["f1"],
        "confusion_matrix": isolation_evaluation["confusion_matrix"],
    }

    primary_model = supervised_models["xgboost"]
    primary_model.fit(features, target)
    probabilities = primary_model.predict_proba(features)[:, 1]
    top_features = generate_shap_outputs(primary_model, features, output_dir)

    predictions = pd.DataFrame(
        {
            "account_id": dataset["account_id"],
            "risk_score": (probabilities * 100).round(2),
            "risk_tier": [assign_risk_tier(score) for score in probabilities * 100],
            "top_3_features": top_features,
        }
    )
    predictions["model_name"] = "xgboost"
    predictions["scored_at"] = pd.Timestamp.utcnow()

    persist_results(predictions, benchmark_results, output_dir)
    LOGGER.info("Model training and scoring completed successfully")
    LOGGER.info("Benchmark summary: %s", json.dumps(benchmark_results, indent=2))


if __name__ == "__main__":
    main()
