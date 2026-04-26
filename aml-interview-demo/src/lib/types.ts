export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type AlertType =
  | "SMURFING"
  | "FAN_OUT"
  | "FAN_IN"
  | "CIRCULAR"
  | "LAYERING"
  | "HIGH_RISK_GEOGRAPHY";

export interface RawAccount {
  account_id: string;
  name: string;
  country: string;
  account_type: string;
}

export interface RawTransaction {
  transaction_id: string;
  timestamp: string;
  sender_account_id: string;
  receiver_account_id: string;
  amount: number;
  currency: string;
  transaction_type: string;
  is_laundering: number;
}

export interface StagedAccount {
  account_id: string;
  account_name: string;
  country: string;
  account_type: string;
  ingestion_timestamp: string;
}

export interface StagedTransaction {
  transaction_id: string;
  transaction_timestamp_utc: string;
  sender_account_id: string;
  receiver_account_id: string;
  amount_original: number;
  amount_eur: number;
  currency: string;
  transaction_type: string;
  is_laundering: number;
  ingestion_timestamp: string;
}

export interface AccountFeature {
  account_id: string;
  total_sent: number;
  total_received: number;
  n_transactions: number;
  avg_amount_sent: number;
  stddev_amount_sent: number;
  n_unique_counterparts: number;
  n_countries_transacted: number;
  ratio_night_transactions: number;
  max_single_transaction: number;
  velocity_7d: number;
  is_laundering_any: number;
}

export interface AlertRecord {
  alert_id: string;
  account_id: string;
  alert_type: AlertType;
  severity: Severity;
  detected_at: string;
  amount_involved: number;
  description: string;
  evidence_transaction_ids: string[];
  accounts_involved: string[];
  threshold: string;
}

export interface SarCandidate {
  account_id: string;
  alert_count: number;
  critical_alert_count: number;
  max_severity: Severity;
  alert_types: string;
  first_alert_at: string;
  latest_alert_at: string;
  total_amount_involved: number;
  sar_rationale: string;
}

export interface GraphMetric {
  account_id: string;
  pagerank_score: number;
  community_id: number;
  degree: number;
  refreshed_at: string;
}

export interface ScoreContribution {
  feature: string;
  direction: "up" | "down";
  impact: number;
  value: number;
}

export interface RiskScore {
  account_id: string;
  risk_score: number;
  risk_tier: Severity;
  top_3_features: string;
  model_name: string;
  scored_at: string;
  shap_like: ScoreContribution[];
}

export interface PipelineStep {
  id: string;
  title: string;
  layer: string;
  input: string;
  transformation: string;
  output: string;
  why_it_matters: string;
  metrics: Array<{ label: string; value: string }>;
}

export interface PipelineArtifacts {
  rawAccounts: RawAccount[];
  rawTransactions: RawTransaction[];
  stagedAccounts: StagedAccount[];
  stagedTransactions: StagedTransaction[];
  features: AccountFeature[];
  alerts: AlertRecord[];
  graphMetrics: GraphMetric[];
  riskScores: RiskScore[];
  sarCandidates: SarCandidate[];
  droppedTransactions: RawTransaction[];
  droppedAccounts: RawAccount[];
}

export interface ScoreSimulationSignal {
  id: string;
  label: string;
  description: string;
  feature: keyof AccountFeature;
  delta: number;
}
