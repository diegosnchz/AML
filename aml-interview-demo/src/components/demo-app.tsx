"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ComponentType, ReactNode } from "react";
import { motion } from "framer-motion";
import clsx from "clsx";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Binary,
  Bot,
  Database,
  FileCode2,
  Gauge,
  GitBranch,
  Play,
  PlayCircle,
  Search,
  Shield,
  Sparkles,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Radar,
  RadarChart,
  PolarAngleAxis,
  PolarGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Core } from "cytoscape";
import {
  buildPipelineSteps,
  EVIDENCE_QUERIES,
  executeEvidenceQuery,
  getAccountAlerts,
  getAccountFeature,
  getAccountRecentTransactions,
  getGraphMetric,
  getRiskScore,
  getTypologyAlerts,
  getTypologyTransactions,
  runPipelineDemo,
  SCORE_SIMULATION_SIGNALS,
  simulateAccountScore,
} from "@/lib/aml-engine";
import { clamp, formatCurrency, formatDate, formatNumber, severityClasses } from "@/lib/format";
import type { AlertRecord, AlertType, Severity } from "@/lib/types";

const CytoscapeGraph = dynamic(() => import("react-cytoscapejs"), {
  ssr: false,
}) as ComponentType<Record<string, unknown>>;

const TYPOLOGIES: Array<{ type: AlertType; label: string; narrative: string }> = [
  {
    type: "SMURFING",
    label: "Smurfing",
    narrative:
      "Fragmentacion sistematica en pagos sub-umbral dentro de 72h para evitar controles de reporte.",
  },
  {
    type: "FAN_IN",
    label: "Fan-in",
    narrative:
      "Consolidacion acelerada desde muchos originadores hacia una cuenta nodo de recoleccion.",
  },
  {
    type: "FAN_OUT",
    label: "Fan-out",
    narrative:
      "Dispersion rapida desde una cuenta distribuidora hacia una red amplia de beneficiarios.",
  },
  {
    type: "CIRCULAR",
    label: "Circular flows",
    narrative:
      "Reciclaje de fondos A->B->C->A en ventana corta para disimular origen y destino economico.",
  },
  {
    type: "LAYERING",
    label: "Layering",
    narrative:
      "Cadenas con step-down controlado (85%-99%) para introducir complejidad y comision encubierta.",
  },
  {
    type: "HIGH_RISK_GEOGRAPHY",
    label: "High-risk geography",
    narrative:
      "Exposicion a jurisdicciones watchlist que activa EDD reforzado y priorizacion investigativa.",
  },
];

const INTERVIEW_SCRIPT = [
  {
    title: "1) Entrada y alcance",
    body: "Empieza por el origen: CSV de cuentas y transacciones, ingesta Python y esquema raw en PostgreSQL.",
    say: "El sistema parte de archivos CSV, los normaliza, deduplica y deja todo trazable para analista.",
  },
  {
    title: "2) Transformaciones dbt",
    body: "Explica staging y features. Muestra como de transacciones crudas pasas a comportamiento por cuenta.",
    say: "No analizo filas sueltas: analizo entidades con features como velocity_7d, ratio nocturna y counterparts.",
  },
  {
    title: "3) Deteccion de tipologias",
    body: "Lanza Alert Lab y activa tipologias una por una con evidencia tabular.",
    say: "Cada alerta enseña umbral, transacciones concretas y cuentas implicadas; no hay texto generico.",
  },
  {
    title: "4) Valor de red",
    body: "Abre la investigacion de grafo para mostrar comunidades, ciclos y cuentas influyentes.",
    say: "Neo4j/GDS agrega senales de red que SQL plano no ve facilmente: hubs, rutas y circuitos.",
  },
  {
    title: "5) Score y explicabilidad",
    body: "En Risk Scoring activa/desactiva senales y enseña como cambia el score en vivo.",
    say: "No es score fijo: puedo simular escenarios y justificar por que sube o baja con contribuciones.",
  },
  {
    title: "6) Cierre investigable",
    body: "Ejecuta SQL Evidence y Data Provenance para dejar claro de donde sale todo.",
    say: "La gracia es que el analista investiga en SQL/BI sin pelear infraestructura ni cajas negras.",
  },
];

const ARCHITECTURE_BLOCKS = [
  "CSV raw",
  "Python ingest",
  "PostgreSQL raw/staging/features/alerts/ml",
  "dbt transformations",
  "Neo4j + GDS",
  "ML scoring + SHAP-like explainability",
  "SQL/BI investigation output",
];

function Badge({ severity }: { severity: Severity }) {
  return (
    <span
      className={clsx(
        "rounded-full border px-2.5 py-1 text-xs font-semibold tracking-[0.16em]",
        severityClasses(severity),
      )}
    >
      {severity}
    </span>
  );
}

function SectionShell({
  id,
  kicker,
  title,
  subtitle,
  children,
}: {
  id: string;
  kicker: string;
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="space-y-4 rounded-3xl border border-[#d5cebf]/70 bg-[#fbf9f3]/65 p-5 md:p-8">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.2em] text-[#9b4a2a]">{kicker}</p>
        <h2 className="text-2xl font-semibold tracking-tight text-[#1f1d18] md:text-3xl">{title}</h2>
        <p className="max-w-4xl text-sm leading-relaxed text-[#4d4940]">{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

export default function DemoApp() {
  const artifacts = useMemo(() => runPipelineDemo(), []);
  const pipelineSteps = useMemo(() => buildPipelineSteps(artifacts), [artifacts]);

  const [pipelineIndex, setPipelineIndex] = useState(-1);
  const [isAutoRunning, setIsAutoRunning] = useState(false);
  const [activeTypology, setActiveTypology] = useState<AlertType>("SMURFING");
  const [selectedAccount, setSelectedAccount] = useState<string>(
    artifacts.riskScores[0]?.account_id ?? artifacts.stagedAccounts[0]?.account_id ?? "",
  );
  const [neighborDepth, setNeighborDepth] = useState<1 | 2>(2);
  const [showCycles, setShowCycles] = useState(true);
  const [showSuspiciousRoutes, setShowSuspiciousRoutes] = useState(true);
  const [riskAccount, setRiskAccount] = useState<string>(
    artifacts.riskScores[0]?.account_id ?? artifacts.stagedAccounts[0]?.account_id ?? "",
  );
  const [activeSignals, setActiveSignals] = useState<string[]>([]);
  const [comparisonAccounts, setComparisonAccounts] = useState<string[]>(
    artifacts.riskScores.slice(0, 3).map((score) => score.account_id),
  );
  const [activeQueryId, setActiveQueryId] = useState(EVIDENCE_QUERIES[0].id);
  const [queryResult, setQueryResult] = useState(() => executeEvidenceQuery(EVIDENCE_QUERIES[0].id, artifacts));
  const [queryRuns, setQueryRuns] = useState(1);
  const [interviewStep, setInterviewStep] = useState(0);
  const [showInterviewNotes, setShowInterviewNotes] = useState(true);

  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!isAutoRunning) return;
    const interval = window.setInterval(() => {
      setPipelineIndex((current) => {
        const next = Math.min(current + 1, pipelineSteps.length - 1);
        if (next >= pipelineSteps.length - 1) {
          setIsAutoRunning(false);
        }
        return next;
      });
    }, 900);
    return () => window.clearInterval(interval);
  }, [isAutoRunning, pipelineSteps.length]);

  const typologyAlerts = useMemo(
    () => getTypologyAlerts(activeTypology, artifacts),
    [activeTypology, artifacts],
  );
  const typologyTransactions = useMemo(
    () => getTypologyTransactions(activeTypology, artifacts),
    [activeTypology, artifacts],
  );

  const selectedAccountFeature = useMemo(
    () => getAccountFeature(selectedAccount, artifacts),
    [selectedAccount, artifacts],
  );
  const selectedAccountAlerts = useMemo(
    () => getAccountAlerts(selectedAccount, artifacts),
    [selectedAccount, artifacts],
  );
  const selectedAccountScore = useMemo(
    () => getRiskScore(selectedAccount, artifacts),
    [selectedAccount, artifacts],
  );
  const selectedGraphMetric = useMemo(
    () => getGraphMetric(selectedAccount, artifacts),
    [selectedAccount, artifacts],
  );
  const selectedRecentTransactions = useMemo(
    () => getAccountRecentTransactions(selectedAccount, artifacts, 8),
    [selectedAccount, artifacts],
  );

  const simulatedScore = useMemo(
    () => simulateAccountScore(riskAccount, activeSignals, artifacts),
    [riskAccount, activeSignals, artifacts],
  );
  const baseScore = useMemo(() => getRiskScore(riskAccount, artifacts), [riskAccount, artifacts]);

  const comparisonRadarData = useMemo(() => {
    return comparisonAccounts
      .map((accountId) => {
        const feature = getAccountFeature(accountId, artifacts);
        const score = getRiskScore(accountId, artifacts);
        if (!feature || !score) return null;
        return {
          accountId,
          risk_score: score.risk_score,
          velocity_7d: feature.velocity_7d,
          counterparts: feature.n_unique_counterparts,
          night_ratio: roundSafe(feature.ratio_night_transactions * 100),
          countries: feature.n_countries_transacted,
        };
      })
      .filter(Boolean) as Array<{
      accountId: string;
      risk_score: number;
      velocity_7d: number;
      counterparts: number;
      night_ratio: number;
      countries: number;
    }>;
  }, [comparisonAccounts, artifacts]);

  const graphElements = useMemo(() => {
    const neighborsLevel1 = new Set<string>();
    const neighborsLevel2 = new Set<string>();
    const cycleTransactionIds = new Set(
      artifacts.alerts
        .filter((alert) => alert.alert_type === "CIRCULAR")
        .flatMap((alert) => alert.evidence_transaction_ids),
    );
    const suspiciousTransactionIds = new Set(
      artifacts.alerts
        .filter((alert) => alert.alert_type !== "HIGH_RISK_GEOGRAPHY")
        .flatMap((alert) => alert.evidence_transaction_ids),
    );

    const selectedDirectEdges = artifacts.stagedTransactions.filter(
      (transaction) =>
        transaction.sender_account_id === selectedAccount || transaction.receiver_account_id === selectedAccount,
    );

    for (const transaction of selectedDirectEdges) {
      const neighbor =
        transaction.sender_account_id === selectedAccount
          ? transaction.receiver_account_id
          : transaction.sender_account_id;
      neighborsLevel1.add(neighbor);
    }

    if (neighborDepth === 2) {
      for (const neighbor of neighborsLevel1) {
        for (const transaction of artifacts.stagedTransactions) {
          if (
            transaction.sender_account_id === neighbor &&
            transaction.receiver_account_id !== selectedAccount
          ) {
            neighborsLevel2.add(transaction.receiver_account_id);
          }
          if (
            transaction.receiver_account_id === neighbor &&
            transaction.sender_account_id !== selectedAccount
          ) {
            neighborsLevel2.add(transaction.sender_account_id);
          }
        }
      }
    }

    const scoreByAccount = new Map(artifacts.riskScores.map((score) => [score.account_id, score]));
    const alertsByAccount = new Map<string, AlertRecord[]>();
    for (const alert of artifacts.alerts) {
      const list = alertsByAccount.get(alert.account_id) ?? [];
      list.push(alert);
      alertsByAccount.set(alert.account_id, list);
    }
    const metricByAccount = new Map(artifacts.graphMetrics.map((metric) => [metric.account_id, metric]));

    const nodeElements = artifacts.stagedAccounts.map((account) => {
      const isSelected = account.account_id === selectedAccount;
      const isL1 = neighborsLevel1.has(account.account_id);
      const isL2 = neighborsLevel2.has(account.account_id);
      const alertCount = alertsByAccount.get(account.account_id)?.length ?? 0;
      const score = scoreByAccount.get(account.account_id)?.risk_score ?? 0;
      const community = metricByAccount.get(account.account_id)?.community_id ?? 0;
      const nodeClass = clsx({
        selected: isSelected,
        neighbor1: isL1,
        neighbor2: isL2,
      });

      return {
        data: {
          id: account.account_id,
          label: account.account_id.replace("ACC-", ""),
          risk: score,
          alertCount,
          community,
        },
        classes: nodeClass,
      };
    });

    const edgeMap = new Map<
      string,
      {
        source: string;
        target: string;
        amount: number;
        count: number;
        hasCycle: boolean;
        hasSuspicion: boolean;
      }
    >();

    for (const transaction of artifacts.stagedTransactions) {
      const edgeId = `${transaction.sender_account_id}->${transaction.receiver_account_id}`;
      const current = edgeMap.get(edgeId) ?? {
        source: transaction.sender_account_id,
        target: transaction.receiver_account_id,
        amount: 0,
        count: 0,
        hasCycle: false,
        hasSuspicion: false,
      };
      current.amount += transaction.amount_eur;
      current.count += 1;
      current.hasCycle = current.hasCycle || cycleTransactionIds.has(transaction.transaction_id);
      current.hasSuspicion =
        current.hasSuspicion || suspiciousTransactionIds.has(transaction.transaction_id);
      edgeMap.set(edgeId, current);
    }

    const edgeElements = Array.from(edgeMap.values()).map((edge, index) => {
      const classes = clsx({
        cycle: showCycles && edge.hasCycle,
        suspicious: showSuspiciousRoutes && edge.hasSuspicion,
      });
      return {
        data: {
          id: `edge-${index}-${edge.source}-${edge.target}`,
          source: edge.source,
          target: edge.target,
          amount: roundSafe(edge.amount),
          count: edge.count,
        },
        classes,
      };
    });

    return [...nodeElements, ...edgeElements];
  }, [
    artifacts,
    selectedAccount,
    neighborDepth,
    showCycles,
    showSuspiciousRoutes,
  ]);

  const cyStylesheet = useMemo(
    () => [
      {
        selector: "node",
        style: {
          "background-color": "#b58a61",
          label: "data(label)",
          width: "mapData(risk, 0, 100, 20, 44)",
          height: "mapData(risk, 0, 100, 20, 44)",
          color: "#1f1d18",
          "font-size": "9px",
          "border-width": "1.5px",
          "border-color": "#8f705a",
          "text-outline-width": "0.8px",
          "text-outline-color": "#f7f5ef",
        },
      },
      {
        selector: "node.selected",
        style: {
          "background-color": "#9b4a2a",
          "border-width": "4px",
          "border-color": "#7c3f26",
        },
      },
      {
        selector: "node.neighbor1",
        style: {
          "background-color": "#8f705a",
          "border-color": "#6f5a4a",
        },
      },
      {
        selector: "node.neighbor2",
        style: {
          "background-color": "#d7cebf",
          "border-color": "#b6ab99",
        },
      },
      {
        selector: "edge",
        style: {
          width: "mapData(amount, 0, 300000, 1, 6)",
          "line-color": "#b6ab99",
          "target-arrow-color": "#b6ab99",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          opacity: 0.7,
        },
      },
      {
        selector: "edge.suspicious",
        style: {
          "line-color": "#c46b45",
          "target-arrow-color": "#c46b45",
          opacity: 0.9,
        },
      },
      {
        selector: "edge.cycle",
        style: {
          "line-color": "#9a3f3f",
          "target-arrow-color": "#9a3f3f",
          "line-style": "dashed",
          opacity: 1,
        },
      },
    ],
    [],
  );

  const pipelineProgress = ((pipelineIndex + 1) / pipelineSteps.length) * 100;

  const scoreDelta = useMemo(() => {
    if (!simulatedScore || !baseScore) return 0;
    return simulatedScore.risk_score - baseScore.risk_score;
  }, [simulatedScore, baseScore]);

  const scrollToDemo = () => {
    const element = document.getElementById("pipeline-replay");
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const executeQuery = () => {
    setQueryResult(executeEvidenceQuery(activeQueryId, artifacts));
    setQueryRuns((current) => current + 1);
  };

  const toggleSignal = (signalId: string) => {
    setActiveSignals((current) =>
      current.includes(signalId)
        ? current.filter((candidate) => candidate !== signalId)
        : [...current, signalId],
    );
  };

  const toggleComparisonAccount = (accountId: string) => {
    setComparisonAccounts((current) => {
      if (current.includes(accountId)) {
        return current.filter((candidate) => candidate !== accountId);
      }
      if (current.length >= 4) {
        return [...current.slice(1), accountId];
      }
      return [...current, accountId];
    });
  };

  const architectureStats = {
    accounts: artifacts.stagedAccounts.length,
    transactions: artifacts.stagedTransactions.length,
    alerts: artifacts.alerts.length,
    sar: artifacts.sarCandidates.length,
  };

  return (
    <main className="min-h-screen bg-[#f7f5ef] text-[#1f1d18]">
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_12%_6%,rgba(196,107,69,.17),transparent_42%),radial-gradient(circle_at_92%_0%,rgba(171,148,121,.2),transparent_36%),linear-gradient(180deg,#faf8f2,#f7f5ef_35%,#f4f0e7)]" />
      <div className="mx-auto max-w-[1400px] space-y-6 px-4 py-6 pb-16 md:px-8">
        <motion.section
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="relative overflow-hidden rounded-3xl border border-[#d5cebf]/70 bg-[#fbf9f3]/75 p-6 md:p-10"
        >
          <div className="absolute right-[-80px] top-[-60px] h-80 w-80 rounded-full bg-[#c46b45]/18 blur-3xl" />
          <div className="absolute left-[35%] top-[55%] h-72 w-72 rounded-full bg-[#ded5c8]/60 blur-3xl" />
          <div className="relative grid gap-8 lg:grid-cols-[1.3fr_1fr]">
            <div className="space-y-6">
              <p className="inline-flex items-center gap-2 rounded-full border border-[#c46b45]/35 bg-[#c46b45]/10 px-3 py-1 text-xs uppercase tracking-[0.18em] text-[#8a3d22]">
                <Sparkles className="h-3.5 w-3.5" />
                Repo-faithful demo
              </p>
              <h1 className="max-w-4xl text-3xl font-semibold leading-tight tracking-tight text-[#1f1d18] md:text-5xl">
                AMLGuardian Interview Ops Console
              </h1>
              <p className="max-w-3xl text-sm leading-relaxed text-[#4d4940] md:text-base">
                Plataforma demo ultra tecnica para explicar de punta a punta un pipeline AML real:
                CSV -&gt; ingesta Python -&gt; PostgreSQL/dbt -&gt; Neo4j + GDS -&gt; scoring ML explicable -&gt;
                investigacion SQL. Cada interaccion recalcula logica y evidencia, sin pantallas
                estaticas.
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <MetricBox icon={Database} label="Cuentas" value={String(architectureStats.accounts)} />
                <MetricBox icon={Binary} label="Transacciones" value={String(architectureStats.transactions)} />
                <MetricBox icon={AlertTriangle} label="Alertas" value={String(architectureStats.alerts)} />
                <MetricBox icon={Shield} label="SAR candidatas" value={String(architectureStats.sar)} />
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={scrollToDemo}
                  className="inline-flex items-center gap-2 rounded-full bg-[#1f1d18] px-5 py-2.5 text-sm font-semibold text-[#f7f5ef] transition hover:bg-[#34312b]"
                >
                  <PlayCircle className="h-4 w-4" />
                  Launch Investigation Demo
                </button>
                <a
                  href="#data-provenance"
                  className="inline-flex items-center gap-2 rounded-full border border-[#d5cebf]/75 px-5 py-2.5 text-sm font-semibold text-[#2a2823] transition hover:border-[#bfb7a6]/90 hover:bg-[#ece6da]/80"
                >
                  <GitBranch className="h-4 w-4" />
                  Data Provenance
                </a>
              </div>
            </div>
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/95 p-4">
              <p className="mb-3 text-xs uppercase tracking-[0.18em] text-[#6f6a5f]">Arquitectura resumida</p>
              <div className="space-y-2">
                {ARCHITECTURE_BLOCKS.map((block, index) => (
                  <div
                    key={block}
                    className="group flex items-center gap-2 rounded-xl border border-[#d5cebf]/70 bg-[#fbf9f3]/75 px-3 py-2 text-sm text-[#2a2823]"
                  >
                    <span className="grid h-6 w-6 place-items-center rounded-md bg-[#c46b45]/18 text-xs font-semibold text-[#8a3d22]">
                      {index + 1}
                    </span>
                    <span>{block}</span>
                    {index < ARCHITECTURE_BLOCKS.length - 1 ? (
                      <ArrowRight className="ml-auto h-3.5 w-3.5 text-[#8a8478] group-hover:text-[#9b4a2a]" />
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.section>

        <SectionShell
          id="pipeline-replay"
          kicker="01. Pipeline Replay"
          title="Run pipeline step by step"
          subtitle="Replica visual del DAG real del repo. Cada paso muestra input, transformacion, output y por que importa."
        >
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setPipelineIndex((current) => Math.min(current + 1, pipelineSteps.length - 1))}
              className="inline-flex items-center gap-2 rounded-full border border-[#c46b45]/35 bg-[#c46b45]/10 px-4 py-2 text-sm font-medium text-[#8a3d22] hover:bg-[#c46b45]/18"
            >
              <Play className="h-4 w-4" />
              Run pipeline step
            </button>
            <button
              onClick={() => {
                setPipelineIndex(-1);
                setIsAutoRunning(true);
              }}
              className="inline-flex items-center gap-2 rounded-full border border-[#8f705a]/35 bg-[#8f705a]/08 px-4 py-2 text-sm font-medium text-[#7c5a45] hover:bg-[#8f705a]/12"
            >
              <Activity className="h-4 w-4" />
              Run full demo
            </button>
            <button
              onClick={() => {
                setPipelineIndex(-1);
                setIsAutoRunning(false);
              }}
              className="inline-flex items-center gap-2 rounded-full border border-[#bfb6a5]/75 px-4 py-2 text-sm font-medium text-[#2a2823] hover:bg-[#ece6da]"
            >
              Reset
            </button>
            <p className="text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">
              {isAutoRunning ? "Auto-running..." : "Manual mode"}
            </p>
          </div>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[#ece6da]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#c46b45] to-[#8f705a] transition-all duration-500"
              style={{ width: `${pipelineProgress}%` }}
            />
          </div>
          <div className="mt-5 grid gap-3 lg:grid-cols-2">
            {pipelineSteps.map((step, index) => {
              const active = index <= pipelineIndex;
              return (
                <div
                  key={step.id}
                  className={clsx(
                    "rounded-2xl border p-4 transition",
                    active
                      ? "border-[#c46b45]/40 bg-[#c46b45]/10"
                      : "border-[#d5cebf]/70 bg-[#f7f4ee]/84",
                  )}
                >
                  <div className="mb-2 flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-[#6f6a5f]">{step.layer}</p>
                      <h3 className="text-lg font-semibold text-[#1f1d18]">{step.title}</h3>
                    </div>
                    <span
                      className={clsx(
                        "rounded-full border px-2 py-1 text-xs font-semibold",
                        active
                          ? "border-[#c46b45]/55 bg-[#c46b45]/18 text-[#8a3d22]"
                          : "border-[#ad9f8a]/80 text-[#6f6a5f]",
                      )}
                    >
                      {active ? "Executed" : "Pending"}
                    </span>
                  </div>
                  <div className="space-y-2 text-sm text-[#4d4940]">
                    <p><span className="font-semibold text-[#2a2823]">Input:</span> {step.input}</p>
                    <p><span className="font-semibold text-[#2a2823]">Transform:</span> {step.transformation}</p>
                    <p><span className="font-semibold text-[#2a2823]">Output:</span> {step.output}</p>
                    <p><span className="font-semibold text-[#2a2823]">Why:</span> {step.why_it_matters}</p>
                  </div>
                  <div className="mt-4 grid gap-2 sm:grid-cols-3">
                    {step.metrics.map((metric) => (
                      <div key={metric.label} className="rounded-xl border border-[#d5cebf]/65 bg-[#fbf9f3]/75 p-2.5">
                        <p className="text-[10px] uppercase tracking-[0.14em] text-[#6f6a5f]">{metric.label}</p>
                        <p className="text-sm font-semibold text-[#1f1d18]">{metric.value}</p>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </SectionShell>

        <SectionShell
          id="alert-lab"
          kicker="02. Alert Lab"
          title="Tipologias AML con evidencia"
          subtitle="Cada tab dispara filtrado y narrativas con transacciones reales del fixture."
        >
          <div className="flex flex-wrap gap-2">
            {TYPOLOGIES.map((typology) => (
              <button
                key={typology.type}
                onClick={() => setActiveTypology(typology.type)}
                className={clsx(
                  "rounded-full border px-3 py-1.5 text-xs font-semibold tracking-[0.14em] transition",
                  activeTypology === typology.type
                    ? "border-[#c46b45]/55 bg-[#c46b45]/18 text-[#8a3d22]"
                    : "border-[#d5cebf]/75 text-[#4d4940] hover:bg-[#ece6da]",
                )}
              >
                {typology.label}
              </button>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/86 p-4">
              <h3 className="text-lg font-semibold text-[#1f1d18]">
                {TYPOLOGIES.find((typology) => typology.type === activeTypology)?.label}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-[#4d4940]">
                {TYPOLOGIES.find((typology) => typology.type === activeTypology)?.narrative}
              </p>
              <div className="mt-4 space-y-3">
                {typologyAlerts.map((alert) => (
                  <div key={alert.alert_id} className="rounded-xl border border-[#d5cebf]/65 bg-[#fbf9f3]/75 p-3">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <p className="font-semibold text-[#1f1d18]">{alert.account_id}</p>
                      <Badge severity={alert.severity} />
                    </div>
                    <p className="text-xs text-[#4d4940]">{alert.description}</p>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <InfoKV label="Threshold" value={alert.threshold} />
                      <InfoKV label="Amount" value={formatCurrency(alert.amount_involved)} />
                      <InfoKV label="Detected at" value={formatDate(alert.detected_at)} />
                      <InfoKV label="Accounts involved" value={String(alert.accounts_involved.length)} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/86 p-4">
              <h4 className="mb-3 text-sm font-semibold uppercase tracking-[0.16em] text-[#6f6a5f]">
                Evidencia transaccional
              </h4>
              <div className="max-h-[360px] overflow-auto rounded-xl border border-[#d5cebf]/65">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-[#fbf9f3]/95 text-[#6f6a5f]">
                    <tr>
                      <th className="px-3 py-2">Tx</th>
                      <th className="px-3 py-2">Timestamp UTC</th>
                      <th className="px-3 py-2">From</th>
                      <th className="px-3 py-2">To</th>
                      <th className="px-3 py-2 text-right">Amount EUR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {typologyTransactions.map((transaction) => (
                      <tr key={transaction.transaction_id} className="border-t border-[#c6bfae]/90 text-[#2a2823]">
                        <td className="px-3 py-2 font-mono">{transaction.transaction_id}</td>
                        <td className="px-3 py-2">{formatDate(transaction.transaction_timestamp_utc)}</td>
                        <td className="px-3 py-2">{transaction.sender_account_id}</td>
                        <td className="px-3 py-2">{transaction.receiver_account_id}</td>
                        <td className="px-3 py-2 text-right">{formatNumber(transaction.amount_eur, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-[#6f6a5f]">
                Investigator narrative:{" "}
                <span className="text-[#2a2823]">
                  {typologyAlerts[0]?.description ??
                    "No evidence for this typology in current data slice."}
                </span>
              </p>
            </div>
          </div>
        </SectionShell>

        <SectionShell
          id="network-investigation"
          kicker="03. Interactive Network Investigation"
          title="Grafo de cuentas y transferencias"
          subtitle="Zoom/pan, foco de vecinos 1er/2do nivel, comunidades, ciclos y rutas sospechosas."
        >
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setNeighborDepth(1)}
              className={clsx(
                "rounded-full border px-3 py-1.5 text-xs font-semibold tracking-[0.14em]",
                neighborDepth === 1
                  ? "border-[#c46b45]/55 bg-[#c46b45]/18 text-[#8a3d22]"
                  : "border-[#d5cebf]/75 text-[#4d4940]",
              )}
            >
              Vecinos 1er nivel
            </button>
            <button
              onClick={() => setNeighborDepth(2)}
              className={clsx(
                "rounded-full border px-3 py-1.5 text-xs font-semibold tracking-[0.14em]",
                neighborDepth === 2
                  ? "border-[#c46b45]/55 bg-[#c46b45]/18 text-[#8a3d22]"
                  : "border-[#d5cebf]/75 text-[#4d4940]",
              )}
            >
              Vecinos 2do nivel
            </button>
            <button
              onClick={() => setShowCycles((current) => !current)}
              className={clsx(
                "rounded-full border px-3 py-1.5 text-xs font-semibold tracking-[0.14em]",
                showCycles
                  ? "border-[#c07575]/45 bg-[#c07575]/16 text-[#8a3d3d]"
                  : "border-[#d5cebf]/75 text-[#4d4940]",
              )}
            >
              Highlight cycles
            </button>
            <button
              onClick={() => setShowSuspiciousRoutes((current) => !current)}
              className={clsx(
                "rounded-full border px-3 py-1.5 text-xs font-semibold tracking-[0.14em]",
                showSuspiciousRoutes
                  ? "border-[#b4743a]/50 bg-[#d09254]/16 text-[#7a4e2a]"
                  : "border-[#d5cebf]/75 text-[#4d4940]",
              )}
            >
              Highlight suspicious routes
            </button>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="h-[540px] rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/92 p-2">
              <CytoscapeGraph
                elements={graphElements}
                layout={{ name: "cose", animate: false, idealEdgeLength: 110, nodeRepulsion: 9000 }}
                style={{ width: "100%", height: "100%" }}
                minZoom={0.35}
                maxZoom={2.2}
                wheelSensitivity={0.2}
                stylesheet={cyStylesheet}
                cy={(cy: Core) => {
                  if (cyRef.current === cy) return;
                  cyRef.current = cy;
                  cy.on("tap", "node", (event) => {
                    const id = event.target.id();
                    setSelectedAccount(id);
                  });
                }}
              />
            </div>
            <div className="space-y-3">
              <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/92 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">Cuenta seleccionada</p>
                <h3 className="mt-1 text-xl font-semibold text-[#1f1d18]">{selectedAccount}</h3>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <InfoKV label="Risk score" value={selectedAccountScore ? String(selectedAccountScore.risk_score) : "-"} />
                  <InfoKV
                    label="Risk tier"
                    value={selectedAccountScore?.risk_tier ?? "LOW"}
                    valueClass={selectedAccountScore ? severityClasses(selectedAccountScore.risk_tier) : ""}
                  />
                  <InfoKV label="Active alerts" value={String(selectedAccountAlerts.length)} />
                  <InfoKV label="PageRank" value={selectedGraphMetric ? String(selectedGraphMetric.pagerank_score) : "-"} />
                  <InfoKV label="Community" value={selectedGraphMetric ? String(selectedGraphMetric.community_id) : "-"} />
                  <InfoKV
                    label="Top features"
                    value={selectedAccountScore?.top_3_features.replaceAll("|", ", ") ?? "-"}
                  />
                </div>
              </div>

              <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/92 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">Features clave</p>
                <div className="mt-2 space-y-2 text-sm text-[#2a2823]">
                  <LineMetric label="velocity_7d" value={selectedAccountFeature?.velocity_7d ?? 0} max={100000} />
                  <LineMetric
                    label="n_unique_counterparts"
                    value={selectedAccountFeature?.n_unique_counterparts ?? 0}
                    max={30}
                  />
                  <LineMetric
                    label="ratio_night_transactions"
                    value={(selectedAccountFeature?.ratio_night_transactions ?? 0) * 100}
                    max={100}
                  />
                  <LineMetric
                    label="n_countries_transacted"
                    value={selectedAccountFeature?.n_countries_transacted ?? 0}
                    max={15}
                  />
                </div>
              </div>

              <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/92 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">Transacciones recientes</p>
                <div className="mt-2 space-y-2 text-xs">
                  {selectedRecentTransactions.map((transaction) => (
                    <div key={transaction.transaction_id} className="rounded-lg border border-[#c6bfae]/85 bg-[#fbf9f3]/85 p-2 text-[#2a2823]">
                      <p className="font-mono">{transaction.transaction_id}</p>
                      <p className="text-[#6f6a5f]">{formatDate(transaction.transaction_timestamp_utc)}</p>
                      <p>
                        {transaction.sender_account_id} -&gt; {transaction.receiver_account_id} |{" "}
                        {formatCurrency(transaction.amount_eur)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </SectionShell>

        <SectionShell
          id="risk-explainability"
          kicker="04. Risk Scoring & Explainability"
          title="Score dinamico y SHAP-like simplificado"
          subtitle="Activa o desactiva senales y observa la recomputacion del score en vivo."
        >
          <div className="grid gap-4 xl:grid-cols-[0.72fr_1.28fr]">
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/86 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">Cuenta para simulacion</p>
              <select
                value={riskAccount}
                onChange={(event) => setRiskAccount(event.target.value)}
                className="mt-2 w-full rounded-xl border border-[#d5cebf]/75 bg-[#fbf9f3] px-3 py-2 text-sm text-[#1f1d18]"
              >
                {artifacts.riskScores.slice(0, 15).map((score) => (
                  <option key={score.account_id} value={score.account_id}>
                    {score.account_id} | {score.risk_score}
                  </option>
                ))}
              </select>

              <div className="mt-4 flex items-center justify-center">
                <ScoreGauge score={simulatedScore?.risk_score ?? 0} />
              </div>

              <div className="mt-3 text-center text-sm">
                <Badge severity={simulatedScore?.risk_tier ?? "LOW"} />
                <p className="mt-2 text-[#4d4940]">
                  Delta vs base:{" "}
                  <span className={clsx(scoreDelta >= 0 ? "text-rose-300" : "text-[#4f7a58]")}>
                    {scoreDelta >= 0 ? "+" : ""}
                    {formatNumber(scoreDelta, 2)}
                  </span>
                </p>
              </div>

              <div className="mt-4 space-y-2">
                {SCORE_SIMULATION_SIGNALS.map((signal) => (
                  <button
                    key={signal.id}
                    onClick={() => toggleSignal(signal.id)}
                    className={clsx(
                      "w-full rounded-xl border p-2 text-left text-xs transition",
                      activeSignals.includes(signal.id)
                        ? "border-[#c46b45]/45 bg-[#c46b45]/15 text-[#8a3d22]"
                        : "border-[#bfb6a5]/75 bg-[#fbf9f3] text-[#4d4940] hover:bg-[#ece6da]",
                    )}
                  >
                    <p className="font-semibold">{signal.label}</p>
                    <p className="text-[11px] text-[#6f6a5f]">{signal.description}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-4">
              <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/86 p-4">
                <p className="mb-2 text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">SHAP-like contributions</p>
                <div className="h-[250px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={(simulatedScore?.shap_like ?? []).map((contribution) => ({
                        feature: contribution.feature,
                        impact:
                          contribution.direction === "up"
                            ? contribution.impact
                            : -contribution.impact,
                      }))}
                      margin={{ left: 0, right: 8, top: 6, bottom: 6 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#d7cebf" />
                      <XAxis dataKey="feature" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <Tooltip contentStyle={{ backgroundColor: "#fffaf1", border: "1px solid #cbbda7" }} />
                      <Bar dataKey="impact">
                        {(simulatedScore?.shap_like ?? []).map((contribution) => (
                          <Cell
                            key={contribution.feature}
                            fill={contribution.direction === "up" ? "#b86a43" : "#6f7a5f"}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/86 p-4">
                <div className="mb-3 flex flex-wrap gap-2">
                  {artifacts.riskScores.slice(0, 8).map((score) => (
                    <button
                      key={score.account_id}
                      onClick={() => toggleComparisonAccount(score.account_id)}
                      className={clsx(
                        "rounded-full border px-3 py-1 text-xs",
                        comparisonAccounts.includes(score.account_id)
                          ? "border-[#8f705a]/45 bg-[#8f705a]/12 text-[#7c5a45]"
                          : "border-[#d5cebf]/75 text-[#4d4940]",
                      )}
                    >
                      {score.account_id}
                    </button>
                  ))}
                </div>
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={buildRadarData(comparisonRadarData)}>
                      <PolarGrid stroke="#d7cebf" />
                      <PolarAngleAxis dataKey="metric" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                      <Legend />
                      {comparisonRadarData.map((entry, index) => (
                        <Radar
                          key={entry.accountId}
                          dataKey={entry.accountId}
                          name={entry.accountId}
                          stroke={["#b86a43", "#8f705a", "#6f7a5f", "#9a3f3f"][index % 4]}
                          fill={["#b86a43", "#8f705a", "#6f7a5f", "#9a3f3f"][index % 4]}
                          fillOpacity={0.15}
                        />
                      ))}
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        </SectionShell>

        <SectionShell
          id="sql-evidence"
          kicker="05. SQL / Evidence View"
          title="Consola investigable sobre data local"
          subtitle="No depende de BD real para la entrevista: ejecuta snippets SQL repo-faithful sobre dataset demo."
        >
          <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/90 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">Query Library</p>
              <div className="mt-3 space-y-2">
                {EVIDENCE_QUERIES.map((query) => (
                  <button
                    key={query.id}
                    onClick={() => setActiveQueryId(query.id)}
                    className={clsx(
                      "w-full rounded-xl border p-3 text-left text-sm transition",
                      activeQueryId === query.id
                        ? "border-[#c46b45]/45 bg-[#c46b45]/15 text-[#8a3d22]"
                        : "border-[#d5cebf]/75 bg-[#fbf9f3]/80 text-[#4d4940] hover:bg-[#ece6da]/80",
                    )}
                  >
                    <p className="font-semibold">{query.title}</p>
                    <p className="mt-1 text-xs text-[#6f6a5f]">{query.description}</p>
                  </button>
                ))}
              </div>
              <button
                onClick={executeQuery}
                className="mt-4 inline-flex items-center gap-2 rounded-full border border-[#c46b45]/45 bg-[#c46b45]/15 px-4 py-2 text-sm font-semibold text-[#8a3d22]"
              >
                <Search className="h-4 w-4" />
                Run query
              </button>
              <p className="mt-2 text-xs text-[#6f6a5f]">Runs: {queryRuns}</p>
            </div>
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/90 p-4">
              <pre className="overflow-auto rounded-xl border border-[#d5cebf]/65 bg-[#fbf9f3]/85 p-3 text-xs leading-relaxed text-[#8a3d22]">
                {EVIDENCE_QUERIES.find((query) => query.id === activeQueryId)?.sql}
              </pre>
              <div className="mt-3 max-h-[320px] overflow-auto rounded-xl border border-[#d5cebf]/65">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-[#fbf9f3]/95 text-[#6f6a5f]">
                    <tr>
                      {queryResult.columns.map((column) => (
                        <th key={column} className="px-3 py-2 font-semibold">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {queryResult.rows.map((row, rowIndex) => (
                      <tr key={`${rowIndex}-${String(row[queryResult.columns[0]])}`} className="border-t border-[#c6bfae]/90 text-[#2a2823]">
                        {queryResult.columns.map((column) => (
                          <td key={`${rowIndex}-${column}`} className="px-3 py-2">
                            {String(row[column])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </SectionShell>

        <SectionShell
          id="interview-mode"
          kicker="06. Interview Mode"
          title="Guion guiado de 3-5 minutos"
          subtitle="Modo narrativo para conducir la entrevista con checkpoints tecnicos y notas de discurso."
        >
          <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/90 p-4">
              <div className="mb-4 flex items-center justify-between">
                <p className="text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">
                  Paso {interviewStep + 1} / {INTERVIEW_SCRIPT.length}
                </p>
                <button
                  onClick={() => setShowInterviewNotes((current) => !current)}
                  className="rounded-full border border-[#d5cebf]/75 px-3 py-1 text-xs text-[#2a2823]"
                >
                  {showInterviewNotes ? "Hide notes" : "Show notes"}
                </button>
              </div>
              <div className="rounded-xl border border-[#d5cebf]/65 bg-[#fbf9f3]/80 p-4">
                <h3 className="text-lg font-semibold text-[#1f1d18]">{INTERVIEW_SCRIPT[interviewStep].title}</h3>
                <p className="mt-2 text-sm text-[#4d4940]">{INTERVIEW_SCRIPT[interviewStep].body}</p>
                {showInterviewNotes ? (
                  <div className="mt-3 rounded-lg border border-[#6b8f72]/30 bg-[#6b8f72]/10 p-3 text-xs text-[#3d5a42]">
                    <p className="font-semibold uppercase tracking-[0.12em]">What to say in interview</p>
                    <p className="mt-1 leading-relaxed">{INTERVIEW_SCRIPT[interviewStep].say}</p>
                  </div>
                ) : null}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  onClick={() => setInterviewStep((current) => Math.max(current - 1, 0))}
                  className="rounded-full border border-[#d5cebf]/75 px-4 py-1.5 text-sm text-[#2a2823]"
                >
                  Previous
                </button>
                <button
                  onClick={() =>
                    setInterviewStep((current) => Math.min(current + 1, INTERVIEW_SCRIPT.length - 1))
                  }
                  className="rounded-full border border-[#c46b45]/45 bg-[#c46b45]/18 px-4 py-1.5 text-sm text-[#8a3d22]"
                >
                  Next
                </button>
              </div>
            </div>
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/90 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-[#6f6a5f]">Roadmap visual</p>
              <div className="mt-3 space-y-2">
                {INTERVIEW_SCRIPT.map((step, index) => (
                  <div
                    key={step.title}
                    className={clsx(
                      "rounded-xl border p-3 text-sm",
                      interviewStep === index
                        ? "border-[#c46b45]/45 bg-[#c46b45]/15 text-[#8a3d22]"
                        : interviewStep > index
                          ? "border-[#6b8f72]/35 bg-[#6b8f72]/10 text-[#2f4a35]"
                          : "border-[#d5cebf]/70 bg-[#fbf9f3]/80 text-[#4d4940]",
                    )}
                  >
                    {step.title}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </SectionShell>

        <SectionShell
          id="data-provenance"
          kicker="07. Data Provenance"
          title="Where the data came from"
          subtitle="Linea de procedencia para dejar claro que no son dashboards desconectados."
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <ProvenanceCard
              icon={FileCode2}
              title="Raw"
              layer="CSV"
              details={[
                "public/fixtures/accounts.csv",
                "public/fixtures/transactions.csv",
                "Campos: account_id, timestamp, amount, currency, is_laundering",
              ]}
            />
            <ProvenanceCard
              icon={Database}
              title="Normalized"
              layer="staging.*"
              details={[
                "staging.stg_accounts",
                "staging.stg_transactions",
                "Dedup + UTC + amount_eur",
              ]}
            />
            <ProvenanceCard
              icon={Bot}
              title="Features"
              layer="features.fct_account_features"
              details={[
                "velocity_7d",
                "ratio_night_transactions",
                "n_unique_counterparts",
              ]}
            />
            <ProvenanceCard
              icon={AlertTriangle}
              title="Alerts"
              layer="alerts.fct_alerts"
              details={[
                "SMURFING/FAN_IN/FAN_OUT",
                "CIRCULAR/LAYERING",
                "HIGH_RISK_GEOGRAPHY",
              ]}
            />
            <ProvenanceCard
              icon={Gauge}
              title="Score"
              layer="ml.risk_scores + ml.graph_account_metrics"
              details={[
                "risk_score (0-100)",
                "risk_tier",
                "pagerank_score + community_id",
              ]}
            />
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/90 p-4">
              <p className="text-sm font-semibold text-[#1f1d18]">What mirrors the real repo</p>
              <ul className="mt-2 space-y-1 text-xs leading-relaxed text-[#4d4940]">
                <li>- Flujo end-to-end: ingest -&gt; dbt -&gt; graph -&gt; ml -&gt; investigation.</li>
                <li>- Tipologias y umbrales del repo (smurfing, fan-in/out, circular, layering, geography).</li>
                <li>- Capas de datos y naming de tablas/schemas (raw/staging/features/alerts/ml).</li>
                <li>- Senales de red tipo PageRank y community_id.</li>
              </ul>
            </div>
            <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/90 p-4">
              <p className="text-sm font-semibold text-[#1f1d18]">What is simulated in this demo</p>
              <ul className="mt-2 space-y-1 text-xs leading-relaxed text-[#4d4940]">
                <li>- Motor TS local en frontend (no ejecuta Airflow/Neo4j/DBT reales durante la demo).</li>
                <li>- Score ML repo-faithful approximation con contribuciones SHAP-like simplificadas.</li>
                <li>- SQL runner sobre dataset local pre-cargado, sin conexion a PostgreSQL real.</li>
                <li>- Community detection aproximada para demo visual (etiquetada como simulada).</li>
              </ul>
            </div>
          </div>
        </SectionShell>
      </div>
    </main>
  );
}

function ProvenanceCard({
  icon: Icon,
  title,
  layer,
  details,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  layer: string;
  details: string[];
}) {
  return (
    <div className="rounded-2xl border border-[#d5cebf]/70 bg-[#f7f4ee]/95 p-4">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-[#9b4a2a]" />
        <p className="font-semibold text-[#1f1d18]">{title}</p>
      </div>
      <p className="mt-1 text-xs text-[#8a3d22]">{layer}</p>
      <ul className="mt-2 space-y-1 text-xs text-[#4d4940]">
        {details.map((detail) => (
          <li key={detail}>- {detail}</li>
        ))}
      </ul>
    </div>
  );
}

function MetricBox({
  icon: Icon,
  label,
  value,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-[#d5cebf]/70 bg-[#f7f4ee]/95 p-3">
      <div className="flex items-center gap-2 text-[#4d4940]">
        <Icon className="h-4 w-4 text-[#9b4a2a]" />
        <p className="text-xs uppercase tracking-[0.14em]">{label}</p>
      </div>
      <p className="mt-2 text-2xl font-semibold text-[#1f1d18]">{value}</p>
    </div>
  );
}

function InfoKV({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-lg border border-[#d5cebf]/65 bg-[#fbf9f3]/80 p-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-[#6f6a5f]">{label}</p>
      <p className={clsx("text-xs text-[#2a2823]", valueClass)}>{value}</p>
    </div>
  );
}

function LineMetric({
  label,
  value,
  max,
}: {
  label: string;
  value: number;
  max: number;
}) {
  const pct = clamp((value / max) * 100, 0, 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-[#4d4940]">
        <span className="font-mono">{label}</span>
        <span>{formatNumber(value, 2)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[#ece6da]">
        <div className="h-full rounded-full bg-[#1f1d18]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ScoreGauge({ score }: { score: number }) {
  const normalized = clamp(score, 0, 100);
  const angle = (normalized / 100) * 360;

  return (
    <div className="relative grid h-40 w-40 place-items-center rounded-full">
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: `conic-gradient(#b86a43 ${angle}deg, rgba(174,161,140,0.22) ${angle}deg)`,
        }}
      />
      <div className="absolute inset-3 rounded-full bg-[#f3efe6]" />
      <div className="relative text-center">
        <p className="text-xs uppercase tracking-[0.14em] text-[#6f6a5f]">Risk score</p>
        <p className="text-3xl font-semibold text-[#1f1d18]">{formatNumber(normalized, 1)}</p>
      </div>
    </div>
  );
}

function buildRadarData(
  entries: Array<{
    accountId: string;
    risk_score: number;
    velocity_7d: number;
    counterparts: number;
    night_ratio: number;
    countries: number;
  }>,
) {
  const metrics = [
    { metric: "risk_score", label: "Risk" },
    { metric: "velocity_7d", label: "Velocity" },
    { metric: "counterparts", label: "Counterparts" },
    { metric: "night_ratio", label: "Night %" },
    { metric: "countries", label: "Countries" },
  ] as const;

  return metrics.map((metric) => {
    const row: Record<string, string | number> = { metric: metric.label };
    for (const entry of entries) {
      row[entry.accountId] = entry[metric.metric];
    }
    return row;
  });
}

function roundSafe(value: number): number {
  return Math.round(value * 100) / 100;
}
