import rawAccounts from "@/data/fixtures/rawAccounts.json";
import rawTransactions from "@/data/fixtures/rawTransactions.json";
import type {
  AccountFeature,
  AlertRecord,
  AlertType,
  GraphMetric,
  PipelineArtifacts,
  PipelineStep,
  RawAccount,
  RawTransaction,
  RiskScore,
  SarCandidate,
  ScoreContribution,
  ScoreSimulationSignal,
  Severity,
  StagedAccount,
  StagedTransaction,
} from "@/lib/types";

const FX_RATES: Record<string, number> = {
  EUR: 1,
  USD: 0.92,
  GBP: 1.17,
  CHF: 1.04,
};

const HIGH_RISK_COUNTRIES = new Set([
  "IRAN",
  "DPRK",
  "MYANMAR",
  "SYRIA",
  "YEMEN",
  "HAITI",
  "SOUTH SUDAN",
  "NIGERIA",
  "VENEZUELA",
  "CAMEROON",
  "CROATIA",
  "KENYA",
  "NAMIBIA",
  "VIETNAM",
  "SOUTH AFRICA",
]);

const ALERT_SEVERITY_ORDER: Record<Severity, number> = {
  LOW: 1,
  MEDIUM: 2,
  HIGH: 3,
  CRITICAL: 4,
};

const SCORE_TIER_BOUNDS: Array<{ bound: number; tier: Severity }> = [
  { bound: 75, tier: "CRITICAL" },
  { bound: 50, tier: "HIGH" },
  { bound: 25, tier: "MEDIUM" },
  { bound: 0, tier: "LOW" },
];

const INGESTION_TIMESTAMP = "2026-04-23T12:00:00Z";

export const SCORE_SIMULATION_SIGNALS: ScoreSimulationSignal[] = [
  {
    id: "ratio_night_boost",
    label: "Ratio nocturna elevada",
    description: "Simula actividad 00:00-06:00 UTC anormalmente alta.",
    feature: "ratio_night_transactions",
    delta: 0.22,
  },
  {
    id: "counterpart_surge",
    label: "Mas contrapartes unicas",
    description: "Simula dispersion/agregacion rapida entre nuevas cuentas.",
    feature: "n_unique_counterparts",
    delta: 6,
  },
  {
    id: "velocity_jump",
    label: "Aceleracion 7d",
    description: "Aumenta la velocidad de volumen transferido en 7 dias.",
    feature: "velocity_7d",
    delta: 24000,
  },
  {
    id: "geo_spread",
    label: "Mas paises involucrados",
    description: "Amplia el alcance geografico de contrapartes.",
    feature: "n_countries_transacted",
    delta: 3,
  },
  {
    id: "large_ticket",
    label: "Ticket maximo superior",
    description: "Incrementa el maximo de operacion individual.",
    feature: "max_single_transaction",
    delta: 18000,
  },
];

export interface EvidenceQuery {
  id: string;
  title: string;
  description: string;
  sql: string;
}

export interface EvidenceResult {
  columns: string[];
  rows: Array<Record<string, string | number>>;
}

interface ScoreContext {
  feature: AccountFeature;
  alerts: AlertRecord[];
  graphMetric?: GraphMetric;
}

export const EVIDENCE_QUERIES: EvidenceQuery[] = [
  {
    id: "top_alerted_accounts",
    title: "Cuentas con mas alertas",
    description: "Prioriza cuentas por volumen de alertas y severidad maxima.",
    sql: `SELECT account_id, COUNT(*) AS alert_count, MAX(severity) AS max_severity, SUM(amount_involved) AS total_amount
FROM alerts.fct_alerts
GROUP BY account_id
ORDER BY alert_count DESC, total_amount DESC
LIMIT 15;`,
  },
  {
    id: "alerts_with_scores",
    title: "Join alertas + risk score",
    description: "Cruza fct_alerts con ml.risk_scores para triage operativo.",
    sql: `SELECT a.account_id, a.alert_type, a.severity, r.risk_score, r.risk_tier, r.top_3_features
FROM alerts.fct_alerts a
JOIN ml.risk_scores r ON a.account_id = r.account_id
ORDER BY r.risk_score DESC, a.detected_at DESC
LIMIT 20;`,
  },
  {
    id: "sar_candidates",
    title: "Candidatas SAR",
    description: "Lista cuentas con >=3 alertas o alguna CRITICAL.",
    sql: `SELECT s.account_id, s.alert_count, s.critical_alert_count, s.max_severity, s.alert_types, s.sar_rationale, r.risk_score, g.pagerank_score
FROM alerts.fct_sar_candidates s
LEFT JOIN ml.risk_scores r ON s.account_id = r.account_id
LEFT JOIN ml.graph_account_metrics g ON s.account_id = g.account_id
ORDER BY s.critical_alert_count DESC, r.risk_score DESC;`,
  },
];

function deterministicId(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  return `ALERT-${Math.abs(hash).toString(16).padStart(8, "0")}`;
}

function toIso(value: Date): string {
  return value.toISOString();
}

function parseDate(value: string): Date | null {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed;
}

function normalizeCurrency(value: string): string {
  return (value || "EUR").trim().toUpperCase() || "EUR";
}

function round(value: number, decimals = 2): number {
  const base = 10 ** decimals;
  return Math.round(value * base) / base;
}

function sampleStdDev(values: number[]): number {
  if (values.length <= 1) {
    return 0;
  }
  const mean = values.reduce((acc, current) => acc + current, 0) / values.length;
  const variance =
    values.reduce((acc, current) => acc + (current - mean) ** 2, 0) /
    (values.length - 1);
  return Math.sqrt(variance);
}

function getSeverityForScore(score: number): Severity {
  return SCORE_TIER_BOUNDS.find((candidate) => score >= candidate.bound)?.tier ?? "LOW";
}

function rankSeverity(values: Severity[]): Severity {
  return values.reduce((highest, current) =>
    ALERT_SEVERITY_ORDER[current] > ALERT_SEVERITY_ORDER[highest] ? current : highest,
  "LOW" as Severity);
}

function unique<T>(values: T[]): T[] {
  return Array.from(new Set(values));
}

function ingestAccounts(raw: RawAccount[]): { staged: StagedAccount[]; dropped: RawAccount[] } {
  const seen = new Set<string>();
  const staged: StagedAccount[] = [];
  const dropped: RawAccount[] = [];

  for (const account of raw) {
    const accountId = (account.account_id || "").trim();
    if (!accountId || seen.has(accountId)) {
      dropped.push(account);
      continue;
    }
    seen.add(accountId);
    staged.push({
      account_id: accountId,
      account_name: (account.name || "UNKNOWN").trim() || "UNKNOWN",
      country: (account.country || "UNKNOWN").trim().toUpperCase() || "UNKNOWN",
      account_type: (account.account_type || "UNKNOWN").trim().toUpperCase() || "UNKNOWN",
      ingestion_timestamp: INGESTION_TIMESTAMP,
    });
  }

  return { staged, dropped };
}

function ingestTransactions(
  raw: RawTransaction[],
): { staged: StagedTransaction[]; dropped: RawTransaction[] } {
  const seen = new Set<string>();
  const staged: StagedTransaction[] = [];
  const dropped: RawTransaction[] = [];

  for (const transaction of raw) {
    const transactionId = (transaction.transaction_id || "").trim();
    const sender = (transaction.sender_account_id || "").trim();
    const receiver = (transaction.receiver_account_id || "").trim();
    const ts = parseDate(transaction.timestamp);
    const amountOriginal = Number(transaction.amount);

    if (
      !transactionId ||
      !sender ||
      !receiver ||
      !ts ||
      Number.isNaN(amountOriginal) ||
      amountOriginal < 0 ||
      seen.has(transactionId)
    ) {
      dropped.push(transaction);
      continue;
    }

    seen.add(transactionId);
    const currency = normalizeCurrency(transaction.currency);
    const fxRate = FX_RATES[currency] ?? 1;

    staged.push({
      transaction_id: transactionId,
      transaction_timestamp_utc: toIso(ts),
      sender_account_id: sender,
      receiver_account_id: receiver,
      amount_original: round(amountOriginal, 2),
      amount_eur: round(amountOriginal * fxRate, 2),
      currency,
      transaction_type: (transaction.transaction_type || "UNKNOWN").trim().toUpperCase() || "UNKNOWN",
      is_laundering: Math.max(0, Math.min(1, Number(transaction.is_laundering) || 0)),
      ingestion_timestamp: INGESTION_TIMESTAMP,
    });
  }

  staged.sort(
    (left, right) =>
      new Date(left.transaction_timestamp_utc).getTime() -
      new Date(right.transaction_timestamp_utc).getTime(),
  );

  return { staged, dropped };
}

function buildFeatures(
  accounts: StagedAccount[],
  transactions: StagedTransaction[],
): AccountFeature[] {
  const accountById = new Map(accounts.map((account) => [account.account_id, account]));
  const latestTimestamp = transactions.at(-1)
    ? new Date(transactions.at(-1)!.transaction_timestamp_utc).getTime()
    : Date.now();

  return accounts.map((account) => {
    const involved = transactions.filter(
      (transaction) =>
        transaction.sender_account_id === account.account_id ||
        transaction.receiver_account_id === account.account_id,
    );
    const sent = involved.filter((transaction) => transaction.sender_account_id === account.account_id);
    const received = involved.filter(
      (transaction) => transaction.receiver_account_id === account.account_id,
    );

    const counterpartIds = involved.map((transaction) =>
      transaction.sender_account_id === account.account_id
        ? transaction.receiver_account_id
        : transaction.sender_account_id,
    );

    const counterpartCountries = counterpartIds
      .map((counterpartId) => accountById.get(counterpartId)?.country ?? "UNKNOWN")
      .filter(Boolean);

    const nightTransactions = involved.filter((transaction) => {
      const hour = new Date(transaction.transaction_timestamp_utc).getUTCHours();
      return hour >= 0 && hour <= 5;
    }).length;

    const sentWithin7d = sent.filter((transaction) => {
      const txTime = new Date(transaction.transaction_timestamp_utc).getTime();
      return txTime >= latestTimestamp - 7 * 24 * 60 * 60 * 1000;
    });

    return {
      account_id: account.account_id,
      total_sent: round(sent.reduce((acc, tx) => acc + tx.amount_eur, 0)),
      total_received: round(received.reduce((acc, tx) => acc + tx.amount_eur, 0)),
      n_transactions: involved.length,
      avg_amount_sent: sent.length
        ? round(sent.reduce((acc, tx) => acc + tx.amount_eur, 0) / sent.length)
        : 0,
      stddev_amount_sent: round(sampleStdDev(sent.map((tx) => tx.amount_eur))),
      n_unique_counterparts: unique(counterpartIds).length,
      n_countries_transacted: unique(counterpartCountries).length,
      ratio_night_transactions: involved.length ? round(nightTransactions / involved.length, 4) : 0,
      max_single_transaction: round(
        involved.length ? Math.max(...involved.map((transaction) => transaction.amount_eur)) : 0,
      ),
      velocity_7d: round(sentWithin7d.reduce((acc, tx) => acc + tx.amount_eur, 0)),
      is_laundering_any: involved.some((transaction) => transaction.is_laundering === 1) ? 1 : 0,
    };
  });
}

function detectSmurfing(transactions: StagedTransaction[]): AlertRecord[] {
  const byAccount = new Map<string, StagedTransaction[]>();
  for (const tx of transactions) {
    if (tx.amount_eur >= 9999) continue;
    const accountTransactions = byAccount.get(tx.sender_account_id) ?? [];
    accountTransactions.push(tx);
    byAccount.set(tx.sender_account_id, accountTransactions);
  }

  const alerts: AlertRecord[] = [];

  byAccount.forEach((accountTransactions, accountId) => {
    accountTransactions.sort(
      (left, right) =>
        new Date(left.transaction_timestamp_utc).getTime() -
        new Date(right.transaction_timestamp_utc).getTime(),
    );

    let best: {
      transactions: StagedTransaction[];
      windowStart: string;
      windowEnd: string;
      amount: number;
    } | null = null;

    for (let index = 0; index < accountTransactions.length; index += 1) {
      const anchor = accountTransactions[index];
      const anchorTime = new Date(anchor.transaction_timestamp_utc).getTime();
      const lowerBound = anchorTime - 72 * 60 * 60 * 1000;
      const windowTx = accountTransactions.filter((candidate) => {
        const candidateTs = new Date(candidate.transaction_timestamp_utc).getTime();
        return candidateTs >= lowerBound && candidateTs <= anchorTime;
      });
      if (windowTx.length < 5) {
        continue;
      }
      const amount = round(windowTx.reduce((acc, candidate) => acc + candidate.amount_eur, 0));
      const windowStart = windowTx[0].transaction_timestamp_utc;
      const windowEnd = anchor.transaction_timestamp_utc;

      if (
        !best ||
        windowTx.length > best.transactions.length ||
        (windowTx.length === best.transactions.length && amount > best.amount)
      ) {
        best = { transactions: windowTx, windowStart, windowEnd, amount };
      }
    }

    if (!best) {
      return;
    }

    const severity: Severity =
      best.transactions.length >= 15
        ? "CRITICAL"
        : best.transactions.length >= 10
          ? "HIGH"
          : "MEDIUM";

    alerts.push({
      alert_id: deterministicId(`${accountId}|SMURFING|${best.windowEnd}`),
      account_id: accountId,
      alert_type: "SMURFING",
      severity,
      detected_at: best.windowEnd,
      amount_involved: best.amount,
      description: `Cuenta ${accountId} envia ${best.transactions.length} pagos por debajo de EUR 9,999 entre ${best.windowStart} y ${best.windowEnd}.`,
      evidence_transaction_ids: best.transactions.map((transaction) => transaction.transaction_id),
      accounts_involved: unique(best.transactions.map((transaction) => transaction.receiver_account_id)),
      threshold: "5+ transacciones sub-EUR 9,999 en ventana rolling de 72h.",
    });
  });

  return alerts;
}

function detectFanOut(transactions: StagedTransaction[]): AlertRecord[] {
  const byAccount = new Map<string, StagedTransaction[]>();
  for (const tx of transactions) {
    const accountTransactions = byAccount.get(tx.sender_account_id) ?? [];
    accountTransactions.push(tx);
    byAccount.set(tx.sender_account_id, accountTransactions);
  }

  const alerts: AlertRecord[] = [];

  byAccount.forEach((accountTransactions, accountId) => {
    let best: {
      anchor: string;
      windowStart: string;
      windowEnd: string;
      amount: number;
      transactions: StagedTransaction[];
      distinctCounterparts: number;
    } | null = null;

    for (const anchor of accountTransactions) {
      const anchorTs = new Date(anchor.transaction_timestamp_utc).getTime();
      const upperBound = anchorTs + 24 * 60 * 60 * 1000;
      const windowTx = accountTransactions.filter((candidate) => {
        const ts = new Date(candidate.transaction_timestamp_utc).getTime();
        return ts >= anchorTs && ts <= upperBound;
      });
      const distinctReceivers = unique(windowTx.map((tx) => tx.receiver_account_id)).length;
      if (distinctReceivers < 10) {
        continue;
      }

      const amount = round(windowTx.reduce((acc, tx) => acc + tx.amount_eur, 0));
      const windowEnd = windowTx
        .map((tx) => tx.transaction_timestamp_utc)
        .sort()
        .at(-1)!;

      if (
        !best ||
        distinctReceivers > best.distinctCounterparts ||
        (distinctReceivers === best.distinctCounterparts && amount > best.amount)
      ) {
        best = {
          anchor: anchor.transaction_id,
          windowStart: anchor.transaction_timestamp_utc,
          windowEnd,
          amount,
          transactions: windowTx,
          distinctCounterparts: distinctReceivers,
        };
      }
    }

    if (!best) {
      return;
    }

    const severity: Severity =
      best.distinctCounterparts >= 20
        ? "CRITICAL"
        : best.distinctCounterparts >= 15
          ? "HIGH"
          : "MEDIUM";

    alerts.push({
      alert_id: deterministicId(`${accountId}|FAN_OUT|${best.anchor}`),
      account_id: accountId,
      alert_type: "FAN_OUT",
      severity,
      detected_at: best.windowEnd,
      amount_involved: best.amount,
      description: `Cuenta ${accountId} distribuye a ${best.distinctCounterparts} beneficiarios unicos en 24h (${best.windowStart} - ${best.windowEnd}).`,
      evidence_transaction_ids: best.transactions.map((transaction) => transaction.transaction_id),
      accounts_involved: unique(best.transactions.map((transaction) => transaction.receiver_account_id)),
      threshold: "10+ receptores unicos en 24h (dispersion fan-out).",
    });
  });

  return alerts;
}

function detectFanIn(transactions: StagedTransaction[]): AlertRecord[] {
  const byAccount = new Map<string, StagedTransaction[]>();
  for (const tx of transactions) {
    const accountTransactions = byAccount.get(tx.receiver_account_id) ?? [];
    accountTransactions.push(tx);
    byAccount.set(tx.receiver_account_id, accountTransactions);
  }

  const alerts: AlertRecord[] = [];

  byAccount.forEach((accountTransactions, accountId) => {
    let best: {
      anchor: string;
      windowStart: string;
      windowEnd: string;
      amount: number;
      transactions: StagedTransaction[];
      distinctCounterparts: number;
    } | null = null;

    for (const anchor of accountTransactions) {
      const anchorTs = new Date(anchor.transaction_timestamp_utc).getTime();
      const upperBound = anchorTs + 24 * 60 * 60 * 1000;
      const windowTx = accountTransactions.filter((candidate) => {
        const ts = new Date(candidate.transaction_timestamp_utc).getTime();
        return ts >= anchorTs && ts <= upperBound;
      });
      const distinctSenders = unique(windowTx.map((tx) => tx.sender_account_id)).length;
      if (distinctSenders < 10) {
        continue;
      }

      const amount = round(windowTx.reduce((acc, tx) => acc + tx.amount_eur, 0));
      const windowEnd = windowTx
        .map((tx) => tx.transaction_timestamp_utc)
        .sort()
        .at(-1)!;

      if (
        !best ||
        distinctSenders > best.distinctCounterparts ||
        (distinctSenders === best.distinctCounterparts && amount > best.amount)
      ) {
        best = {
          anchor: anchor.transaction_id,
          windowStart: anchor.transaction_timestamp_utc,
          windowEnd,
          amount,
          transactions: windowTx,
          distinctCounterparts: distinctSenders,
        };
      }
    }

    if (!best) {
      return;
    }

    const severity: Severity =
      best.distinctCounterparts >= 20
        ? "CRITICAL"
        : best.distinctCounterparts >= 15
          ? "HIGH"
          : "MEDIUM";

    alerts.push({
      alert_id: deterministicId(`${accountId}|FAN_IN|${best.anchor}`),
      account_id: accountId,
      alert_type: "FAN_IN",
      severity,
      detected_at: best.windowEnd,
      amount_involved: best.amount,
      description: `Cuenta ${accountId} agrega fondos de ${best.distinctCounterparts} originadores unicos en 24h (${best.windowStart} - ${best.windowEnd}).`,
      evidence_transaction_ids: best.transactions.map((transaction) => transaction.transaction_id),
      accounts_involved: unique(best.transactions.map((transaction) => transaction.sender_account_id)),
      threshold: "10+ emisores unicos en 24h (consolidacion fan-in).",
    });
  });

  return alerts;
}

function detectCircular(transactions: StagedTransaction[]): AlertRecord[] {
  const bySender = new Map<string, StagedTransaction[]>();
  for (const tx of transactions) {
    const list = bySender.get(tx.sender_account_id) ?? [];
    list.push(tx);
    bySender.set(tx.sender_account_id, list);
  }

  const cyclesByRoot = new Map<
    string,
    {
      txs: StagedTransaction[];
      amount: number;
      detectedAt: string;
    }
  >();

  for (const first of transactions) {
    if (first.sender_account_id === first.receiver_account_id) continue;

    const secondCandidates = bySender.get(first.receiver_account_id) ?? [];
    const firstTs = new Date(first.transaction_timestamp_utc).getTime();

    for (const second of secondCandidates) {
      const secondTs = new Date(second.transaction_timestamp_utc).getTime();
      if (secondTs < firstTs || secondTs > firstTs + 7 * 24 * 60 * 60 * 1000) continue;
      if (second.receiver_account_id === first.sender_account_id) continue;
      if (second.receiver_account_id === first.receiver_account_id) continue;

      const thirdCandidates = bySender.get(second.receiver_account_id) ?? [];
      for (const third of thirdCandidates) {
        const thirdTs = new Date(third.transaction_timestamp_utc).getTime();
        if (thirdTs < secondTs || thirdTs > firstTs + 7 * 24 * 60 * 60 * 1000) continue;
        if (third.receiver_account_id !== first.sender_account_id) continue;

        const amount = round(first.amount_eur + second.amount_eur + third.amount_eur);
        const root = first.sender_account_id;
        const existing = cyclesByRoot.get(root);
        if (!existing || amount > existing.amount) {
          cyclesByRoot.set(root, {
            txs: [first, second, third],
            amount,
            detectedAt: third.transaction_timestamp_utc,
          });
        }
      }
    }
  }

  const alerts: AlertRecord[] = [];
  for (const [accountId, cycle] of cyclesByRoot) {
    const severity: Severity =
      cycle.amount >= 100000 ? "CRITICAL" : cycle.amount >= 50000 ? "HIGH" : "MEDIUM";
    const path = [
      cycle.txs[0].sender_account_id,
      cycle.txs[0].receiver_account_id,
      cycle.txs[1].receiver_account_id,
      cycle.txs[2].receiver_account_id,
    ];

    alerts.push({
      alert_id: deterministicId(`${accountId}|CIRCULAR|${cycle.txs.map((tx) => tx.transaction_id).join("|")}`),
      account_id: accountId,
      alert_type: "CIRCULAR",
      severity,
      detected_at: cycle.detectedAt,
      amount_involved: cycle.amount,
      description: `Flujo circular detectado ${path[0]} -> ${path[1]} -> ${path[2]} -> ${path[3]} en <= 7 dias.`,
      evidence_transaction_ids: cycle.txs.map((tx) => tx.transaction_id),
      accounts_involved: unique(path),
      threshold: "Ciclo A->B->C->A completado en <= 7 dias.",
    });
  }

  return alerts;
}

function detectLayering(transactions: StagedTransaction[]): AlertRecord[] {
  const bySender = new Map<string, StagedTransaction[]>();
  for (const tx of transactions) {
    const list = bySender.get(tx.sender_account_id) ?? [];
    list.push(tx);
    bySender.set(tx.sender_account_id, list);
  }

  type Chain = {
    root: string;
    txs: StagedTransaction[];
    accounts: string[];
    amount: number;
    depth: number;
    detectedAt: string;
  };

  const chainsByRoot = new Map<string, Chain>();

  function dfs(currentChain: Chain): void {
    if (currentChain.depth >= 3) {
      const existing = chainsByRoot.get(currentChain.root);
      if (
        !existing ||
        currentChain.depth > existing.depth ||
        (currentChain.depth === existing.depth && currentChain.amount > existing.amount)
      ) {
        chainsByRoot.set(currentChain.root, { ...currentChain });
      }
    }

    if (currentChain.depth >= 5) return;

    const lastTx = currentChain.txs.at(-1)!;
    const nextCandidates = bySender.get(lastTx.receiver_account_id) ?? [];
    const lastTs = new Date(lastTx.transaction_timestamp_utc).getTime();

    for (const next of nextCandidates) {
      const nextTs = new Date(next.transaction_timestamp_utc).getTime();
      if (nextTs < lastTs || nextTs > lastTs + 48 * 60 * 60 * 1000) continue;
      if (currentChain.accounts.includes(next.receiver_account_id)) continue;

      const lower = lastTx.amount_eur * 0.85;
      const upper = lastTx.amount_eur * 0.99;
      if (next.amount_eur < lower || next.amount_eur > upper) continue;

      dfs({
        root: currentChain.root,
        txs: [...currentChain.txs, next],
        accounts: [...currentChain.accounts, next.receiver_account_id],
        amount: round(currentChain.amount + next.amount_eur),
        depth: currentChain.depth + 1,
        detectedAt: next.transaction_timestamp_utc,
      });
    }
  }

  for (const tx of transactions) {
    if (tx.sender_account_id === tx.receiver_account_id) continue;
    dfs({
      root: tx.sender_account_id,
      txs: [tx],
      accounts: [tx.sender_account_id, tx.receiver_account_id],
      amount: tx.amount_eur,
      depth: 1,
      detectedAt: tx.transaction_timestamp_utc,
    });
  }

  const alerts: AlertRecord[] = [];
  for (const [accountId, chain] of chainsByRoot) {
    if (chain.depth < 3) continue;

    const severity: Severity =
      chain.depth >= 5 ? "CRITICAL" : chain.depth === 4 ? "HIGH" : "MEDIUM";

    alerts.push({
      alert_id: deterministicId(`${accountId}|LAYERING|${chain.txs.map((tx) => tx.transaction_id).join("|")}`),
      account_id: accountId,
      alert_type: "LAYERING",
      severity,
      detected_at: chain.detectedAt,
      amount_involved: round(chain.amount),
      description: `Cadena layering de profundidad ${chain.depth} con retencion 85%-99% por salto (${chain.accounts.join(" -> ")}).`,
      evidence_transaction_ids: chain.txs.map((tx) => tx.transaction_id),
      accounts_involved: chain.accounts,
      threshold: "Cadena >= 3 transferencias secuenciales con step-down 85%-99% y <=48h por salto.",
    });
  }

  return alerts;
}

function detectHighRiskGeography(
  accounts: StagedAccount[],
  transactions: StagedTransaction[],
): AlertRecord[] {
  const accountCountry = new Map(accounts.map((account) => [account.account_id, account.country]));
  const exposures = new Map<
    string,
    {
      amount: number;
      detectedAt: string;
      exposureCount: number;
      countries: Set<string>;
      txIds: string[];
      counterparties: Set<string>;
    }
  >();

  for (const tx of transactions) {
    const senderCountry = accountCountry.get(tx.sender_account_id) ?? "UNKNOWN";
    const receiverCountry = accountCountry.get(tx.receiver_account_id) ?? "UNKNOWN";

    const senderRisky = HIGH_RISK_COUNTRIES.has(senderCountry);
    const receiverRisky = HIGH_RISK_COUNTRIES.has(receiverCountry);
    if (!senderRisky && !receiverRisky) continue;

    const senderExposure = exposures.get(tx.sender_account_id) ?? {
      amount: 0,
      detectedAt: tx.transaction_timestamp_utc,
      exposureCount: 0,
      countries: new Set<string>(),
      txIds: [],
      counterparties: new Set<string>(),
    };
    senderExposure.amount += tx.amount_eur;
    senderExposure.detectedAt =
      new Date(tx.transaction_timestamp_utc) > new Date(senderExposure.detectedAt)
        ? tx.transaction_timestamp_utc
        : senderExposure.detectedAt;
    senderExposure.exposureCount += 1;
    senderExposure.countries.add(senderRisky ? senderCountry : receiverCountry);
    senderExposure.txIds.push(tx.transaction_id);
    senderExposure.counterparties.add(tx.receiver_account_id);
    exposures.set(tx.sender_account_id, senderExposure);

    const receiverExposure = exposures.get(tx.receiver_account_id) ?? {
      amount: 0,
      detectedAt: tx.transaction_timestamp_utc,
      exposureCount: 0,
      countries: new Set<string>(),
      txIds: [],
      counterparties: new Set<string>(),
    };
    receiverExposure.amount += tx.amount_eur;
    receiverExposure.detectedAt =
      new Date(tx.transaction_timestamp_utc) > new Date(receiverExposure.detectedAt)
        ? tx.transaction_timestamp_utc
        : receiverExposure.detectedAt;
    receiverExposure.exposureCount += 1;
    receiverExposure.countries.add(receiverRisky ? receiverCountry : senderCountry);
    receiverExposure.txIds.push(tx.transaction_id);
    receiverExposure.counterparties.add(tx.sender_account_id);
    exposures.set(tx.receiver_account_id, receiverExposure);
  }

  const alerts: AlertRecord[] = [];
  for (const [accountId, exposure] of exposures) {
    const severity: Severity =
      exposure.exposureCount >= 10
        ? "CRITICAL"
        : exposure.exposureCount >= 5
          ? "HIGH"
          : "MEDIUM";

    alerts.push({
      alert_id: deterministicId(`${accountId}|HIGH_RISK_GEOGRAPHY`),
      account_id: accountId,
      alert_type: "HIGH_RISK_GEOGRAPHY",
      severity,
      detected_at: exposure.detectedAt,
      amount_involved: round(exposure.amount),
      description: `Cuenta ${accountId} expuesta a jurisdicciones de riesgo (${Array.from(exposure.countries).sort().join(", ")}) en ${exposure.exposureCount} transferencias.`,
      evidence_transaction_ids: unique(exposure.txIds),
      accounts_involved: Array.from(exposure.counterparties),
      threshold: "Exposicion a watchlist FATF/EBA hardcodeada en el modelo dbt.",
    });
  }

  return alerts;
}

function buildGraphMetrics(
  accounts: StagedAccount[],
  transactions: StagedTransaction[],
): GraphMetric[] {
  const ids = accounts.map((account) => account.account_id);
  const n = ids.length;
  const idIndex = new Map(ids.map((id, index) => [id, index]));

  const outboundWeight = new Map<string, number>();
  const edgeWeight = new Map<string, number>();
  const undirectedNeighbors = new Map<string, Set<string>>();

  for (const tx of transactions) {
    const edgeKey = `${tx.sender_account_id}->${tx.receiver_account_id}`;
    edgeWeight.set(edgeKey, (edgeWeight.get(edgeKey) ?? 0) + tx.amount_eur);
    outboundWeight.set(
      tx.sender_account_id,
      (outboundWeight.get(tx.sender_account_id) ?? 0) + tx.amount_eur,
    );

    if (!undirectedNeighbors.has(tx.sender_account_id)) {
      undirectedNeighbors.set(tx.sender_account_id, new Set<string>());
    }
    if (!undirectedNeighbors.has(tx.receiver_account_id)) {
      undirectedNeighbors.set(tx.receiver_account_id, new Set<string>());
    }
    undirectedNeighbors.get(tx.sender_account_id)!.add(tx.receiver_account_id);
    undirectedNeighbors.get(tx.receiver_account_id)!.add(tx.sender_account_id);
  }

  let pagerank = Array.from({ length: n }, () => 1 / n);
  for (let iteration = 0; iteration < 50; iteration += 1) {
    const next = Array.from({ length: n }, () => (1 - 0.85) / n);
    let danglingMass = 0;

    for (const from of ids) {
      const out = outboundWeight.get(from) ?? 0;
      const fromIndex = idIndex.get(from)!;
      if (out === 0) {
        danglingMass += pagerank[fromIndex];
        continue;
      }

      for (const to of ids) {
        const weight = edgeWeight.get(`${from}->${to}`) ?? 0;
        if (weight === 0) continue;
        const toIndex = idIndex.get(to)!;
        next[toIndex] += 0.85 * pagerank[fromIndex] * (weight / out);
      }
    }

    if (danglingMass > 0) {
      const share = (0.85 * danglingMass) / n;
      for (let i = 0; i < n; i += 1) {
        next[i] += share;
      }
    }

    pagerank = next;
  }

  const labels = new Map<string, string>(ids.map((id) => [id, id]));
  for (let iteration = 0; iteration < 8; iteration += 1) {
    for (const id of ids) {
      const neighbors = Array.from(undirectedNeighbors.get(id) ?? []);
      if (!neighbors.length) continue;

      const counts = new Map<string, number>();
      for (const neighbor of neighbors) {
        const label = labels.get(neighbor)!;
        counts.set(label, (counts.get(label) ?? 0) + 1);
      }

      const best = Array.from(counts.entries()).sort(
        (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
      )[0];
      if (best) {
        labels.set(id, best[0]);
      }
    }
  }

  const labelToCommunity = new Map<string, number>();
  let communityCounter = 0;

  return ids
    .map((accountId) => {
      const label = labels.get(accountId) ?? accountId;
      if (!labelToCommunity.has(label)) {
        labelToCommunity.set(label, communityCounter);
        communityCounter += 1;
      }

      const index = idIndex.get(accountId)!;
      return {
        account_id: accountId,
        pagerank_score: round(pagerank[index], 6),
        community_id: labelToCommunity.get(label)!,
        degree: (undirectedNeighbors.get(accountId) ?? new Set<string>()).size,
        refreshed_at: INGESTION_TIMESTAMP,
      };
    })
    .sort((left, right) => right.pagerank_score - left.pagerank_score);
}

function scoreFromContext(context: ScoreContext): { score: number; contributions: ScoreContribution[] } {
  const { feature, alerts, graphMetric } = context;
  const criticalAlerts = alerts.filter((alert) => alert.severity === "CRITICAL").length;
  const highAlerts = alerts.filter((alert) => alert.severity === "HIGH").length;
  const mediumAlerts = alerts.filter((alert) => alert.severity === "MEDIUM").length;
  const typologySpread = unique(alerts.map((alert) => alert.alert_type)).length;
  const pagerank = graphMetric?.pagerank_score ?? 0;

  const contributions: ScoreContribution[] = [
    {
      feature: "velocity_7d",
      direction: "up",
      impact: round(Math.min(34, feature.velocity_7d / 1600), 2),
      value: feature.velocity_7d,
    },
    {
      feature: "n_unique_counterparts",
      direction: "up",
      impact: round(Math.min(18, feature.n_unique_counterparts * 1.65), 2),
      value: feature.n_unique_counterparts,
    },
    {
      feature: "ratio_night_transactions",
      direction: "up",
      impact: round(feature.ratio_night_transactions * 19, 2),
      value: feature.ratio_night_transactions,
    },
    {
      feature: "n_countries_transacted",
      direction: "up",
      impact: round(Math.min(11, feature.n_countries_transacted * 1.25), 2),
      value: feature.n_countries_transacted,
    },
    {
      feature: "alert_intensity",
      direction: "up",
      impact: round(criticalAlerts * 12 + highAlerts * 7 + mediumAlerts * 4 + typologySpread * 2.5, 2),
      value: alerts.length,
    },
    {
      feature: "pagerank_score",
      direction: "up",
      impact: round(Math.min(15, pagerank * 800), 2),
      value: pagerank,
    },
    {
      feature: "total_received_stability",
      direction: "down",
      impact: round(Math.min(8, feature.total_received / 45000), 2),
      value: feature.total_received,
    },
  ];

  const raw =
    8 +
    contributions
      .map((contribution) =>
        contribution.direction === "up" ? contribution.impact : -contribution.impact,
      )
      .reduce((acc, current) => acc + current, 0);

  const normalized = Math.max(0, Math.min(100, round(raw, 2)));
  return { score: normalized, contributions };
}

function buildRiskScores(
  features: AccountFeature[],
  alerts: AlertRecord[],
  graphMetrics: GraphMetric[],
): RiskScore[] {
  const alertsByAccount = new Map<string, AlertRecord[]>();
  for (const alert of alerts) {
    const list = alertsByAccount.get(alert.account_id) ?? [];
    list.push(alert);
    alertsByAccount.set(alert.account_id, list);
  }

  const graphByAccount = new Map(graphMetrics.map((metric) => [metric.account_id, metric]));

  return features
    .map((feature) => {
      const accountAlerts = alertsByAccount.get(feature.account_id) ?? [];
      const graphMetric = graphByAccount.get(feature.account_id);
      const { score, contributions } = scoreFromContext({
        feature,
        alerts: accountAlerts,
        graphMetric,
      });
      const topThree = contributions
        .filter((contribution) => contribution.direction === "up")
        .sort((left, right) => right.impact - left.impact)
        .slice(0, 3)
        .map((contribution) => contribution.feature)
        .join("|");

      return {
        account_id: feature.account_id,
        risk_score: score,
        risk_tier: getSeverityForScore(score),
        top_3_features: topThree,
        model_name: "xgboost_repo_faithful_demo",
        scored_at: INGESTION_TIMESTAMP,
        shap_like: contributions,
      };
    })
    .sort((left, right) => right.risk_score - left.risk_score);
}

function buildSarCandidates(alerts: AlertRecord[]): SarCandidate[] {
  const byAccount = new Map<string, AlertRecord[]>();
  for (const alert of alerts) {
    const list = byAccount.get(alert.account_id) ?? [];
    list.push(alert);
    byAccount.set(alert.account_id, list);
  }

  const candidates: SarCandidate[] = [];

  for (const [accountId, accountAlerts] of byAccount) {
    const alertCount = accountAlerts.length;
    const criticalCount = accountAlerts.filter((alert) => alert.severity === "CRITICAL").length;
    if (alertCount < 3 && criticalCount === 0) {
      continue;
    }

    const severity = rankSeverity(accountAlerts.map((alert) => alert.severity));
    const orderedByDate = [...accountAlerts].sort(
      (left, right) =>
        new Date(left.detected_at).getTime() - new Date(right.detected_at).getTime(),
    );

    candidates.push({
      account_id: accountId,
      alert_count: alertCount,
      critical_alert_count: criticalCount,
      max_severity: severity,
      alert_types: unique(accountAlerts.map((alert) => alert.alert_type)).sort().join(", "),
      first_alert_at: orderedByDate[0].detected_at,
      latest_alert_at: orderedByDate[orderedByDate.length - 1].detected_at,
      total_amount_involved: round(
        accountAlerts.reduce((acc, alert) => acc + alert.amount_involved, 0),
      ),
      sar_rationale:
        criticalCount > 0
          ? "CRITICAL severity alert present"
          : "Three or more alert typologies accumulated",
    });
  }

  return candidates.sort((left, right) =>
    right.critical_alert_count - left.critical_alert_count || right.alert_count - left.alert_count,
  );
}

export function runPipelineDemo(): PipelineArtifacts {
  const rawAccountsTyped = rawAccounts as RawAccount[];
  const rawTransactionsTyped = rawTransactions as RawTransaction[];

  const accountsIngestion = ingestAccounts(rawAccountsTyped);
  const transactionsIngestion = ingestTransactions(rawTransactionsTyped);

  const features = buildFeatures(accountsIngestion.staged, transactionsIngestion.staged);
  const smurfing = detectSmurfing(transactionsIngestion.staged);
  const fanOut = detectFanOut(transactionsIngestion.staged);
  const fanIn = detectFanIn(transactionsIngestion.staged);
  const circular = detectCircular(transactionsIngestion.staged);
  const layering = detectLayering(transactionsIngestion.staged);
  const geography = detectHighRiskGeography(
    accountsIngestion.staged,
    transactionsIngestion.staged,
  );

  const alerts = [smurfing, fanOut, fanIn, circular, layering, geography]
    .flat()
    .sort(
      (left, right) =>
        new Date(right.detected_at).getTime() - new Date(left.detected_at).getTime(),
    );

  const graphMetrics = buildGraphMetrics(accountsIngestion.staged, transactionsIngestion.staged);
  const riskScores = buildRiskScores(features, alerts, graphMetrics);
  const sarCandidates = buildSarCandidates(alerts);

  return {
    rawAccounts: rawAccountsTyped,
    rawTransactions: rawTransactionsTyped,
    stagedAccounts: accountsIngestion.staged,
    stagedTransactions: transactionsIngestion.staged,
    features,
    alerts,
    graphMetrics,
    riskScores,
    sarCandidates,
    droppedTransactions: transactionsIngestion.dropped,
    droppedAccounts: accountsIngestion.dropped,
  };
}

export function buildPipelineSteps(artifacts: PipelineArtifacts): PipelineStep[] {
  const alertCountByType = artifacts.alerts.reduce<Record<string, number>>((acc, alert) => {
    acc[alert.alert_type] = (acc[alert.alert_type] ?? 0) + 1;
    return acc;
  }, {});

  return [
    {
      id: "csv_ingest",
      title: "CSV Raw Ingestion",
      layer: "Python scripts/ingest.py",
      input: "data/accounts.csv + data/transactions.csv",
      transformation:
        "Normalizacion de cabeceras, conversion FX a EUR (EUR/USD/GBP/CHF), timestamps a UTC y limpieza de nulos.",
      output: "raw.accounts + raw.transactions",
      why_it_matters: "Garantiza trazabilidad de origen y consistencia para dbt.",
      metrics: [
        { label: "Filas raw transacciones", value: String(artifacts.rawTransactions.length) },
        { label: "Filas descartadas", value: String(artifacts.droppedTransactions.length) },
        { label: "Filas cargadas", value: String(artifacts.stagedTransactions.length) },
      ],
    },
    {
      id: "staging",
      title: "dbt Staging",
      layer: "dbt/models/staging",
      input: "raw.transactions + raw.accounts",
      transformation:
        "Deduplicacion por transaction_id/account_id y estandarizacion de tipos/currency/country.",
      output: "staging.stg_transactions + staging.stg_accounts",
      why_it_matters: "Evita ruido y da una capa limpia para features y reglas.",
      metrics: [
        { label: "stg_accounts", value: String(artifacts.stagedAccounts.length) },
        { label: "stg_transactions", value: String(artifacts.stagedTransactions.length) },
        { label: "Monedas detectadas", value: String(unique(artifacts.stagedTransactions.map((tx) => tx.currency)).length) },
      ],
    },
    {
      id: "features",
      title: "Feature Mart",
      layer: "dbt/models/marts/features/fct_account_features.sql",
      input: "staging.*",
      transformation:
        "Agregaciones por cuenta: volumen, counterparties, night ratio, velocity_7d, paises y max transaction.",
      output: "features.fct_account_features",
      why_it_matters: "Concentra comportamiento AML por cuenta para scoring y analisis.",
      metrics: [
        { label: "Cuentas con features", value: String(artifacts.features.length) },
        { label: "Media counterparts", value: round(artifacts.features.reduce((acc, feature) => acc + feature.n_unique_counterparts, 0) / artifacts.features.length, 2).toString() },
        { label: "Media ratio nocturna", value: round(artifacts.features.reduce((acc, feature) => acc + feature.ratio_night_transactions, 0) / artifacts.features.length, 3).toString() },
      ],
    },
    {
      id: "alerts",
      title: "Alert Rules",
      layer: "dbt/models/marts/alerts",
      input: "features + staging",
      transformation:
        "Reglas de smurfing, fan-in/out, circular, layering y geografia de riesgo.",
      output: "alerts.fct_alerts + alerts.fct_sar_candidates",
      why_it_matters: "Expone tipologias AML explicables y accionables para analista.",
      metrics: [
        { label: "Alertas totales", value: String(artifacts.alerts.length) },
        { label: "Tipos detectados", value: String(unique(artifacts.alerts.map((alert) => alert.alert_type)).length) },
        { label: "SAR candidates", value: String(artifacts.sarCandidates.length) },
      ],
    },
    {
      id: "graph",
      title: "Neo4j + GDS",
      layer: "scripts/load_graph.py",
      input: "staging.stg_accounts + staging.stg_transactions",
      transformation:
        "Carga grafo Account-TRANSFERRED, ejecuta PageRank y community detection tipo Louvain.",
      output: "ml.graph_account_metrics",
      why_it_matters: "Anade senales de red para hubs, clusters y flujos circulares.",
      metrics: [
        { label: "Nodos", value: String(artifacts.stagedAccounts.length) },
        { label: "Comunidades", value: String(unique(artifacts.graphMetrics.map((metric) => metric.community_id)).length) },
        {
          label: "Top PageRank",
          value: `${artifacts.graphMetrics[0]?.account_id ?? "-"} (${artifacts.graphMetrics[0]?.pagerank_score ?? 0})`,
        },
      ],
    },
    {
      id: "scoring",
      title: "ML Scoring + Explainability",
      layer: "scripts/train_model.py",
      input: "features + alerts + graph metrics",
      transformation:
        "Scoring XGBoost repo-faithful demo con contribuciones tipo SHAP simplificadas.",
      output: "ml.risk_scores + outputs/risk_scores.csv + outputs/shap_summary.png",
      why_it_matters: "Prioriza investigacion y aporta explicabilidad por feature.",
      metrics: [
        { label: "Cuentas puntuadas", value: String(artifacts.riskScores.length) },
        {
          label: "Tier CRITICAL",
          value: String(artifacts.riskScores.filter((score) => score.risk_tier === "CRITICAL").length),
        },
        {
          label: "Top score",
          value: `${artifacts.riskScores[0]?.account_id ?? "-"} (${artifacts.riskScores[0]?.risk_score ?? 0})`,
        },
      ],
    },
    {
      id: "investigation",
      title: "Investigation Output",
      layer: "sql/investigations + BI",
      input: "alerts + scores + graph + SQL evidence",
      transformation:
        "Cruce de alertas con score y red para narrativa investigable y priorizacion SAR.",
      output: "vista analista SQL/BI lista para entrevista",
      why_it_matters: "El analista investiga sin pelearse con infraestructura.",
      metrics: [
        {
          label: "Tipologias activas",
          value: Object.entries(alertCountByType)
            .map(([type, count]) => `${type}:${count}`)
            .join(" | "),
        },
        {
          label: "SAR rationale",
          value: artifacts.sarCandidates[0]?.sar_rationale ?? "No threshold reached",
        },
        {
          label: "Tiempo demo",
          value: "3-5 min interview mode",
        },
      ],
    },
  ];
}

export function executeEvidenceQuery(queryId: string, artifacts: PipelineArtifacts): EvidenceResult {
  if (queryId === "top_alerted_accounts") {
    const grouped = artifacts.alerts.reduce<
      Map<string, { alert_count: number; max_severity: Severity; total_amount: number }>
    >((acc, alert) => {
      const current = acc.get(alert.account_id) ?? {
        alert_count: 0,
        max_severity: "LOW",
        total_amount: 0,
      };
      current.alert_count += 1;
      current.max_severity =
        ALERT_SEVERITY_ORDER[alert.severity] > ALERT_SEVERITY_ORDER[current.max_severity]
          ? alert.severity
          : current.max_severity;
      current.total_amount += alert.amount_involved;
      acc.set(alert.account_id, current);
      return acc;
    }, new Map());

    const rows = Array.from(grouped.entries())
      .map(([accountId, values]) => ({
        account_id: accountId,
        alert_count: values.alert_count,
        max_severity: values.max_severity,
        total_amount: round(values.total_amount),
      }))
      .sort(
        (left, right) =>
          right.alert_count - left.alert_count ||
          ALERT_SEVERITY_ORDER[right.max_severity as Severity] -
            ALERT_SEVERITY_ORDER[left.max_severity as Severity],
      )
      .slice(0, 15);

    return {
      columns: ["account_id", "alert_count", "max_severity", "total_amount"],
      rows,
    };
  }

  if (queryId === "alerts_with_scores") {
    const scoreByAccount = new Map(artifacts.riskScores.map((score) => [score.account_id, score]));

    const rows = artifacts.alerts
      .map((alert) => {
        const score = scoreByAccount.get(alert.account_id);
        return {
          account_id: alert.account_id,
          alert_type: alert.alert_type,
          severity: alert.severity,
          risk_score: score?.risk_score ?? 0,
          risk_tier: score?.risk_tier ?? "LOW",
          top_3_features: score?.top_3_features ?? "",
        };
      })
      .sort((left, right) => (right.risk_score as number) - (left.risk_score as number))
      .slice(0, 20);

    return {
      columns: ["account_id", "alert_type", "severity", "risk_score", "risk_tier", "top_3_features"],
      rows,
    };
  }

  const scoreByAccount = new Map(artifacts.riskScores.map((score) => [score.account_id, score]));
  const graphByAccount = new Map(
    artifacts.graphMetrics.map((metric) => [metric.account_id, metric]),
  );

  const rows = artifacts.sarCandidates.map((candidate) => ({
    account_id: candidate.account_id,
    alert_count: candidate.alert_count,
    critical_alert_count: candidate.critical_alert_count,
    max_severity: candidate.max_severity,
    alert_types: candidate.alert_types,
    sar_rationale: candidate.sar_rationale,
    risk_score: scoreByAccount.get(candidate.account_id)?.risk_score ?? 0,
    pagerank_score: graphByAccount.get(candidate.account_id)?.pagerank_score ?? 0,
  }));

  return {
    columns: [
      "account_id",
      "alert_count",
      "critical_alert_count",
      "max_severity",
      "alert_types",
      "sar_rationale",
      "risk_score",
      "pagerank_score",
    ],
    rows,
  };
}

export function getAccountFeature(accountId: string, artifacts: PipelineArtifacts): AccountFeature | undefined {
  return artifacts.features.find((feature) => feature.account_id === accountId);
}

export function getAccountAlerts(accountId: string, artifacts: PipelineArtifacts): AlertRecord[] {
  return artifacts.alerts.filter((alert) => alert.account_id === accountId);
}

export function getAccountRecentTransactions(
  accountId: string,
  artifacts: PipelineArtifacts,
  limit = 8,
): StagedTransaction[] {
  return artifacts.stagedTransactions
    .filter(
      (transaction) =>
        transaction.sender_account_id === accountId || transaction.receiver_account_id === accountId,
    )
    .sort(
      (left, right) =>
        new Date(right.transaction_timestamp_utc).getTime() -
        new Date(left.transaction_timestamp_utc).getTime(),
    )
    .slice(0, limit);
}

export function getRiskScore(accountId: string, artifacts: PipelineArtifacts): RiskScore | undefined {
  return artifacts.riskScores.find((score) => score.account_id === accountId);
}

export function getGraphMetric(accountId: string, artifacts: PipelineArtifacts): GraphMetric | undefined {
  return artifacts.graphMetrics.find((metric) => metric.account_id === accountId);
}

export function simulateAccountScore(
  accountId: string,
  activeSignalIds: string[],
  artifacts: PipelineArtifacts,
): RiskScore | null {
  const baseFeature = getAccountFeature(accountId, artifacts);
  if (!baseFeature) {
    return null;
  }

  const nextFeature: AccountFeature = { ...baseFeature };
  for (const signalId of activeSignalIds) {
    const signal = SCORE_SIMULATION_SIGNALS.find((candidate) => candidate.id === signalId);
    if (!signal) continue;
    const currentValue = Number(nextFeature[signal.feature]);
    if (!Number.isFinite(currentValue)) {
      continue;
    }
    nextFeature[signal.feature] = round(currentValue + signal.delta, 4) as never;
  }

  if (nextFeature.ratio_night_transactions > 1) {
    nextFeature.ratio_night_transactions = 1;
  }

  const alerts = getAccountAlerts(accountId, artifacts);
  const graphMetric = getGraphMetric(accountId, artifacts);
  const scoring = scoreFromContext({
    feature: nextFeature,
    alerts,
    graphMetric,
  });

  return {
    account_id: accountId,
    risk_score: scoring.score,
    risk_tier: getSeverityForScore(scoring.score),
    top_3_features: scoring.contributions
      .filter((contribution) => contribution.direction === "up")
      .sort((left, right) => right.impact - left.impact)
      .slice(0, 3)
      .map((contribution) => contribution.feature)
      .join("|"),
    model_name: "xgboost_repo_faithful_demo",
    scored_at: INGESTION_TIMESTAMP,
    shap_like: scoring.contributions,
  };
}

export function getTypologyAlerts(
  alertType: AlertType,
  artifacts: PipelineArtifacts,
): AlertRecord[] {
  return artifacts.alerts.filter((alert) => alert.alert_type === alertType);
}

export function getTypologyTransactions(
  alertType: AlertType,
  artifacts: PipelineArtifacts,
): StagedTransaction[] {
  const alertTransactions = getTypologyAlerts(alertType, artifacts)
    .flatMap((alert) => alert.evidence_transaction_ids);
  const txIds = new Set(alertTransactions);
  return artifacts.stagedTransactions.filter((transaction) => txIds.has(transaction.transaction_id));
}

export function getAccountCatalog(artifacts: PipelineArtifacts): Array<{
  account_id: string;
  account_name: string;
  country: string;
  account_type: string;
}> {
  return artifacts.stagedAccounts.map((account) => ({
    account_id: account.account_id,
    account_name: account.account_name,
    country: account.country,
    account_type: account.account_type,
  }));
}
