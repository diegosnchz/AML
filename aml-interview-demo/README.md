# AMLGuardian Interview Demo

Demo web **repo-faithful** para entrevistas AML basada en el repositorio `diegosnchz/AML`.

## Ejecutar local

```bash
cd aml-interview-demo
npm install
npm run dev
```

Abrir en: [http://localhost:3000](http://localhost:3000)

Build de producción:

```bash
npm run build
npm run start
```

## Qué incluye

- Home / Executive Overview
- Pipeline Replay (step-by-step + full run)
- Alert Lab por tipología AML
- Interactive Network Investigation (Cytoscape)
- Risk Scoring & Explainability (score dinámico + SHAP-like)
- SQL / Evidence View (queries ejecutadas sobre data demo local)
- Interview Mode guiado (3-5 minutos)
- Data Provenance (raw -> staging -> features -> alerts -> score)

## Datos demo incluidos

- JSON:
  - `src/data/fixtures/rawAccounts.json`
  - `src/data/fixtures/rawTransactions.json`
- CSV:
  - `public/fixtures/accounts.csv`
  - `public/fixtures/transactions.csv`

## What Is Simulated vs What Mirrors The Real Repo

### Mirrors the real repo

- Flujo end-to-end: `ingest -> dbt -> alerts -> graph -> ml -> investigation`.
- Tipologías y umbrales alineados con modelos dbt del repositorio:
  - Smurfing, Fan-in, Fan-out, Circular, Layering, High-risk geography.
- Naming y capas de datos (`raw/staging/features/alerts/ml`).
- Señales de red tipo PageRank / community_id.

### Simulated in this demo

- No ejecuta Airflow, dbt, PostgreSQL ni Neo4j en vivo durante la demo web.
- Score ML en frontend como aproximación explainable (`xgboost_repo_faithful_demo`).
- SHAP simplificado (contribuciones feature-level).
- SQL runner local sobre fixtures (sin conexión a base real).
- Community detection aproximada para experiencia interactiva.

## Despliegue en Vercel

El proyecto es compatible con despliegue directo en Vercel:

1. Importar carpeta `aml-interview-demo`.
2. Framework detectado: Next.js.
3. Build command: `npm run build`.
4. Output: default de Next.js.
