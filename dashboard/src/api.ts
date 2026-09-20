import { SEED_REOPENS, seedDetails } from "./seed";
import type {
  Capa, CapaIn, Category, Check, Closure, Detail, FishboneEntry, Metrics, NcStatus, Nonconformance,
  NonconformanceIn, Rca, Suggestion, WhyStep,
} from "./types";

export interface Backend {
  readonly mode: "api" | "seed";
  /** Base URL for the PDF / JSON closure links (null in seed mode: no server to link to). */
  readonly base: string | null;
  list(): Promise<Nonconformance[]>;
  detail(id: string): Promise<Detail>;
  metrics(): Promise<Metrics>;
  suggest(description: string): Promise<Suggestion>;
  createNc(body: NonconformanceIn): Promise<Nonconformance>;
  createRca(body: Omit<Rca, "confidence_band">): Promise<void>;
  createCapa(body: CapaIn): Promise<void>;
  recordCheck(body: Check): Promise<void>;
  close(body: Closure): Promise<void>;
}

const API = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

async function call<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, body === undefined ? undefined : {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${path}: ${((await r.json()) as { detail?: string }).detail ?? ""}`);
  return (await r.json()) as T;
}

const remote: Backend = {
  mode: "api",
  base: API,
  list: () => call("/nonconformances"),
  detail: (id) => call(`/nonconformance/${id}`),
  metrics: () => call("/metrics"),
  suggest: (d) => call(`/rca/suggest?description=${encodeURIComponent(d)}`),
  createNc: (b) => call("/nonconformance", b),
  createRca: (b) => call("/rca", b),
  createCapa: (b) => call("/capa", b),
  recordCheck: (b) => call("/effectiveness-check", b),
  close: (b) => call("/close", b),
};

// ---- seed mode: the workflow runs in memory so the Pages demo is clickable ----------------------
// ponytail: a compact port of app/rca.py's keyword table + band routing and app/workflow.py's
// transitions. Local state only, no persistence; a reload restores the seed.
const KEYWORDS: Record<Category, Record<string, number>> = {
  Method: { "torque spec": 3, "work instruction": 3, sop: 3, procedure: 2, "process step": 2, specification: 1, spec: 1 },
  Machine: { fixture: 3, "tool wear": 3, spindle: 3, "calibration drift": 2, machine: 2, press: 2, equipment: 1 },
  Material: { supplier: 3, "raw material": 3, contamination: 3, lot: 2, component: 2, batch: 2 },
  Manpower: { training: 3, trained: 3, fatigue: 3, handover: 3, shift: 2, operator: 1 },
  Measurement: { gauge: 3, "r&r": 3, cmm: 3, calibration: 2, inspection: 2, measurement: 2 },
  Environment: { humidity: 3, temperature: 3, esd: 3, lighting: 3, vibration: 3, cleanroom: 3 },
};
const CLARIFY =
  "I can't tell which category this is yet. Was the problem tied to how the work is done (Method), the equipment (Machine), the parts (Material), the people (Manpower), how it was measured (Measurement), or the surroundings (Environment)?";
const ROOT_MARKERS = ["no procedure", "not defined", "not trained", "no requirement", "not specified", "missing", "never", "lacks", "absence of"];
const SYMPTOM_MARKERS = ["because it broke", "failed", "was wrong", "defective"];
const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

export function bandFor(c: number): Suggestion["band"] {
  return c >= 0.8 ? "HIGH" : c >= 0.55 ? "AMBIGUOUS" : "LOW";
}

export function suggestLocal(description: string): Suggestion {
  const text = description.toLowerCase();
  const scores = (Object.entries(KEYWORDS) as [Category, Record<string, number>][]).map(([cat, table]) => [
    cat,
    Object.entries(table).reduce((n, [kw, w]) => (new RegExp(`\\b${escapeRe(kw)}\\b`).test(text) ? n + w : n), 0),
  ] as [Category, number]);
  const ranked = scores.filter(([, s]) => s > 0).sort((a, b) => b[1] - a[1]).slice(0, 2);
  const total = scores.reduce((n, [, s]) => n + s, 0);
  const top = ranked[0]?.[1] ?? 0;
  const confidence = total ? Math.round((top / total) * Math.min(1, top / 3) * 1000) / 1000 : 0;
  const band = bandFor(confidence);
  return {
    candidates: ranked.map(([c, s]) => [c, Math.round((s / total) * 1000) / 1000]),
    confidence,
    band,
    suggested: band === "HIGH" ? ranked[0][0] : null,
    prompt: band === "LOW" ? CLARIFY : null,
  };
}

function looksLikeRootCause(answer: string): Detail["why_flags"][number] {
  const t = answer.toLowerCase();
  for (const m of ROOT_MARKERS) if (t.includes(m)) return { reads_systemic: true, reason: `'${m}' names a missing system element (reads as root cause)` };
  for (const m of SYMPTOM_MARKERS) if (t.includes(m)) return { reads_systemic: false, reason: `'${m}' restates the failure (reads as symptom); ask why again` };
  return { reads_systemic: false, reason: "no systemic marker found; ask why again" };
}

const TRANSITIONS: Record<NcStatus, NcStatus[]> = {
  open: ["rca_in_progress"],
  rca_in_progress: ["capa_assigned"],
  capa_assigned: ["effectiveness_pending"],
  effectiveness_pending: ["closed", "capa_assigned"],
  closed: [],
};
const month = (d: string) => d.slice(0, 7);
const nextId = (prefix: string, ids: string[]) => `${prefix}-${1 + Math.max(0, ...ids.map((i) => Number(i.split("-")[1])))}`;
const addDays = (d: string, n: number) => new Date(new Date(d).getTime() + n * 86_400_000).toISOString().slice(0, 10);
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;

export function localBackend(): Backend {
  const details = clone(seedDetails);
  let reopens = SEED_REOPENS;
  const byId = (id: string) => {
    const d = details.find((x) => x.nonconformance.id === id);
    if (!d) throw new Error(`404 not found: ${id}`);
    return d;
  };
  const byCapa = (capaId: string) => {
    const d = details.find((x) => x.capa?.id === capaId);
    if (!d) throw new Error(`404 not found: ${capaId}`);
    return d;
  };
  const move = (d: Detail, to: NcStatus) => {
    const from = d.nonconformance.status;
    if (!TRANSITIONS[from].includes(to)) throw new Error(`409 ${d.nonconformance.id}: ${from} -> ${to} is not allowed`);
    d.nonconformance.status = to;
  };
  return {
    mode: "seed",
    base: null,
    list: async () => clone(details.map((d) => d.nonconformance)),
    detail: async (id) => clone(byId(id)),
    metrics: async () => {
      const count = (keys: string[]) => keys.sort().reduce<Record<string, number>>((m, k) => ({ ...m, [k]: (m[k] ?? 0) + 1 }), {});
      const by_status = { open: 0, rca_in_progress: 0, capa_assigned: 0, effectiveness_pending: 0, closed: 0 };
      for (const d of details) by_status[d.nonconformance.status] += 1;
      return {
        open: details.length - by_status.closed,
        closed: by_status.closed,
        by_status,
        opened_by_month: count(details.map((d) => month(d.nonconformance.detected_date))),
        closed_by_month: count(details.filter((d) => d.closure).map((d) => month(d.closure!.closed_date))),
        reopened: reopens,
      };
    },
    suggest: async (description) => suggestLocal(description),
    createNc: async (body) => {
      const nc: Nonconformance = { id: nextId("NC", details.map((d) => d.nonconformance.id)), ...body, status: "open" };
      details.push({ nonconformance: nc, rca: null, why_flags: [], capa: null, checks: [], closure: null });
      return clone(nc);
    },
    createRca: async (body) => {
      const d = byId(body.nonconformance_id);
      const s = suggestLocal(d.nonconformance.description);
      const rca: Rca = { ...body };
      if (rca.suggested_category === null && rca.confidence === null) {
        rca.confidence = s.confidence;
        rca.suggested_category = s.suggested;
      }
      rca.confidence_band = rca.confidence === null ? null : bandFor(rca.confidence);
      move(d, "rca_in_progress");
      d.rca = rca;
      d.why_flags = rca.method === "5-why" ? (rca.steps as WhyStep[]).map((st) => looksLikeRootCause(st.answer)) : [];
    },
    createCapa: async (body) => {
      const d = byId(body.nonconformance_id);
      const id = nextId("CAPA", details.flatMap((x) => (x.capa ? [x.capa.id] : [])));
      if (d.nonconformance.status !== "capa_assigned") move(d, "capa_assigned"); // reopened: revised CAPA replaces
      const capa: Capa = { id, ...body, status: "planned" };
      d.capa = capa;
      d.checks = [{
        capa_id: id,
        check_date: addDays(body.due_date, 30),
        method: "30-day post-implementation effectiveness review",
        result: "pending",
        evidence_uri: null,
      }];
      move(d, "effectiveness_pending");
    },
    recordCheck: async (body) => {
      const d = byCapa(body.capa_id);
      if (body.result === "not_effective") {
        move(d, "capa_assigned");
        reopens += 1;
      }
      d.checks = [{ ...body }];
    },
    close: async (body) => {
      const d = byCapa(body.capa_id);
      const chk = d.checks[0];
      if (chk?.result !== "effective") throw new Error(`409 ${d.nonconformance.id}: cannot close, effectiveness result is ${chk?.result ?? "none"}`);
      move(d, "closed");
      d.closure = { ...body };
    },
  };
}

/** Seed when built for Pages (non-root base) or when the API does not answer /health. */
export async function connect(): Promise<Backend> {
  if (import.meta.env.BASE_URL !== "/") return localBackend();
  try {
    const r = await fetch(`${API}/health`);
    if (r.ok) return remote;
  } catch { /* fall through */ }
  return localBackend();
}

export type { FishboneEntry, WhyStep };
