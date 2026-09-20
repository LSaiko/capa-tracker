// TS mirrors of schemas/models.py and the app/main.py response shapes.
export type Band = "HIGH" | "AMBIGUOUS" | "LOW";
export type NcStatus = "open" | "rca_in_progress" | "capa_assigned" | "effectiveness_pending" | "closed";
export type Source = "audit" | "complaint" | "internal" | "supplier";
export type Severity = "minor" | "major" | "critical";
export type Category = "Method" | "Machine" | "Material" | "Manpower" | "Measurement" | "Environment";
export type CheckResult = "effective" | "not_effective" | "pending";

export const STATUSES: [NcStatus, string][] = [
  ["open", "Open"],
  ["rca_in_progress", "RCA in progress"],
  ["capa_assigned", "CAPA assigned"],
  ["effectiveness_pending", "Effectiveness pending"],
  ["closed", "Closed"],
];
export const CATEGORIES: Category[] = ["Method", "Machine", "Material", "Manpower", "Measurement", "Environment"];

export interface Nonconformance {
  id: string;
  description: string;
  source: Source;
  severity: Severity;
  detected_date: string;
  status: NcStatus;
}
export interface NonconformanceIn extends Omit<Nonconformance, "id" | "status"> {}

export interface WhyStep { question: string; answer: string }
export interface FishboneEntry { category: Category; cause: string }
export interface Rca {
  nonconformance_id: string;
  method: "5-why" | "fishbone";
  steps: WhyStep[] | FishboneEntry[];
  suggested_category: Category | null;
  confidence: number | null;
  confidence_band?: Band | null;
  root_cause_text: string;
}
export interface WhyFlag { reads_systemic: boolean; reason: string }

export interface Capa {
  id: string;
  nonconformance_id: string;
  action_description: string;
  owner: string;
  due_date: string;
  status: "planned" | "in_progress" | "done";
}
export interface CapaIn extends Omit<Capa, "id" | "status"> {}

export interface Check {
  capa_id: string;
  check_date: string;
  method: string;
  result: CheckResult;
  evidence_uri: string | null;
}
export interface Closure {
  capa_id: string;
  closed_date: string;
  closed_by: string;
  linked_requirement_ids: string[];
}

export interface Suggestion {
  candidates: [Category, number][];
  confidence: number;
  band: Band;
  suggested: Category | null;
  prompt: string | null;
}

/** GET /nonconformance/{id} */
export interface Detail {
  nonconformance: Nonconformance;
  rca: Rca | null;
  why_flags: WhyFlag[];
  capa: Capa | null;
  checks: Check[];
  closure: Closure | null;
}

/** GET /metrics */
export interface Metrics {
  open: number;
  closed: number;
  by_status: Record<NcStatus, number>;
  opened_by_month: Record<string, number>;
  closed_by_month: Record<string, number>;
  reopened: number;
}
