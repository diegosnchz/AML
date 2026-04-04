from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from neo4j import GraphDatabase
from sqlalchemy import text

from common import configure_logging, env, get_engine


LOGGER = configure_logging("amlguardian.graph")
BATCH_SIZE = 10_000


def neo4j_driver():
    return GraphDatabase.driver(
        env("NEO4J_URI", "bolt://neo4j:7687"),
        auth=(env("NEO4J_USERNAME", required=True), env("NEO4J_PASSWORD", required=True)),
    )


def reset_graph(session) -> None:
    session.run(
        "CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE"
    )
    session.run("MATCH (n) DETACH DELETE n")


def load_accounts(session, accounts: list[dict]) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (a:Account {id: row.account_id})
        SET a.name = row.account_name,
            a.country = row.country,
            a.account_type = row.account_type,
            a.risk_score = coalesce(a.risk_score, 0.0)
        """,
        rows=accounts,
    )


def load_transactions(session, transactions: list[dict]) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (s:Account {id: row.sender_account_id})
        MATCH (r:Account {id: row.receiver_account_id})
        CREATE (s)-[:TRANSFERRED {
            transaction_id: row.transaction_id,
            amount_eur: row.amount_eur,
            currency: row.currency,
            timestamp: datetime(row.transaction_timestamp_utc),
            is_laundering: row.is_laundering
        }]->(r)
        """,
        rows=transactions,
    )


def build_graph_projection(session) -> None:
    exists = session.run(
        "CALL gds.graph.exists('amlguardian_graph') YIELD exists RETURN exists"
    ).single()
    if exists and exists["exists"]:
        session.run("CALL gds.graph.drop('amlguardian_graph', false)")

    session.run(
        """
        CALL gds.graph.project(
            'amlguardian_graph',
            'Account',
            {
                TRANSFERRED: {
                    orientation: 'NATURAL',
                    properties: ['amount_eur', 'is_laundering']
                }
            }
        )
        """
    )
    session.run(
        """
        CALL gds.pageRank.write(
            'amlguardian_graph',
            {
                writeProperty: 'pagerank_score',
                maxIterations: 50,
                dampingFactor: 0.85
            }
        )
        """
    )
    session.run(
        """
        CALL gds.louvain.write(
            'amlguardian_graph',
            {
                writeProperty: 'community_id'
            }
        )
        """
    )


def fetch_graph_metrics(session) -> pd.DataFrame:
    result = session.run(
        """
        MATCH (a:Account)
        RETURN a.id AS account_id,
               coalesce(a.pagerank_score, 0.0) AS pagerank_score,
               coalesce(a.community_id, -1) AS community_id
        ORDER BY pagerank_score DESC
        """
    )
    rows = [record.data() for record in result]
    metrics = pd.DataFrame(rows)
    metrics["refreshed_at"] = datetime.now(tz=UTC)
    return metrics


def persist_graph_metrics(metrics: pd.DataFrame) -> None:
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS ml"))
        connection.execute(text("DROP TABLE IF EXISTS ml.graph_account_metrics"))
    metrics.to_sql(
        "graph_account_metrics",
        engine,
        schema="ml",
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5_000,
    )


def main() -> None:
    engine = get_engine()
    driver = neo4j_driver()
    LOGGER.info("Loading staged account and transaction network into Neo4j")

    with driver.session(database=env("NEO4J_DATABASE", "neo4j")) as session:
        reset_graph(session)

        for accounts_chunk in pd.read_sql(
            """
            SELECT account_id, account_name, country, account_type
            FROM staging.stg_accounts
            ORDER BY account_id
            """,
            engine,
            chunksize=BATCH_SIZE,
        ):
            load_accounts(session, accounts_chunk.to_dict("records"))
        LOGGER.info("Account nodes loaded into Neo4j")

        for transactions_chunk in pd.read_sql(
            """
            SELECT transaction_id,
                   sender_account_id,
                   receiver_account_id,
                   amount_eur,
                   currency,
                   to_char(transaction_timestamp_utc AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS') || 'Z' AS transaction_timestamp_utc,
                   is_laundering
            FROM staging.stg_transactions
            ORDER BY transaction_timestamp_utc
            """,
            engine,
            chunksize=BATCH_SIZE,
        ):
            load_transactions(session, transactions_chunk.to_dict("records"))
        LOGGER.info("Transaction relationships loaded into Neo4j")

        build_graph_projection(session)
        metrics = fetch_graph_metrics(session)

    persist_graph_metrics(metrics)
    top_accounts = metrics.sort_values("pagerank_score", ascending=False).head(20)
    LOGGER.info("Top 20 accounts by PageRank:\n%s", top_accounts.to_string(index=False))
    driver.close()
    LOGGER.info("Neo4j graph load completed successfully")


if __name__ == "__main__":
    main()
