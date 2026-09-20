import { CategoryScale, Chart, Legend, LinearScale, LineController, LineElement, PointElement, Tooltip } from "chart.js";
import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Backend } from "./api";
import {
  CATEGORIES, STATUSES, type Band, type Category, type CheckResult, type Detail, type FishboneEntry, type Metrics,
  type Nonconformance, type NonconformanceIn, type Rca, type Suggestion, type WhyStep,
} from "./types";

Chart.register(CategoryScale, LinearScale, LineController, LineElement, PointElement, Tooltip, Legend);

export const BAND_COLOR: Record<Band, string> = { HIGH: "#22d3ee", AMBIGUOUS: "#f97316", LOW: "#94a3b8" };
const today = () => new Date().toISOString().slice(0, 10);
const label = (s: string) => s.replace(/_/g, " ");

export const Chip = ({ band, text }: { band: Band; text?: string }) => (
  <span className="chip" style={{ background: BAND_COLOR[band] }}>{text ?? band}</span>
);

// ---- board -------------------------------------------------------------------------------------

export function Board({ ncs, onSelect }: { ncs: Nonconformance[]; onSelect: (id: string) => void }) {
  return (
    <div className="board">
      {STATUSES.map(([status, title]) => (
        <div key={status} className="column">
          <h3>{title} <span className="muted">{ncs.filter((n) => n.status === status).length}</span></h3>
          {ncs.filter((n) => n.status === status).map((n) => (
            <button key={n.id} className={`card sev-${n.severity}`} onClick={() => onSelect(n.id)}>
              <div className="card-head"><code>{n.id}</code><span className="muted small">{n.severity} · {n.source}</span></div>
              <div className="small">{n.description.length > 110 ? `${n.description.slice(0, 110)}…` : n.description}</div>
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

// ---- metrics -----------------------------------------------------------------------------------

export function MetricsPanel({ m }: { m: Metrics }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvas.current) return;
    const months = [...new Set([...Object.keys(m.opened_by_month), ...Object.keys(m.closed_by_month)])].sort();
    const chart = new Chart(canvas.current, {
      type: "line",
      data: {
        labels: months,
        datasets: [
          { label: "opened", data: months.map((k) => m.opened_by_month[k] ?? 0), borderColor: "#22d3ee", backgroundColor: "#22d3ee", tension: 0.2 },
          { label: "closed", data: months.map((k) => m.closed_by_month[k] ?? 0), borderColor: "#94a3b8", backgroundColor: "#94a3b8", tension: 0.2 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: "#94a3b8" } } },
        scales: {
          x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.15)" } },
          y: { beginAtZero: true, ticks: { color: "#94a3b8", precision: 0 }, grid: { color: "rgba(148,163,184,0.15)" } },
        },
      },
    });
    return () => chart.destroy();
  }, [m]);
  return (
    <div className="metrics">
      <div className="tiles">
        <div className="tile" style={{ borderColor: "#22d3ee" }}><div className="tile-value" style={{ color: "#22d3ee" }}>{m.open}</div><div className="muted">open</div></div>
        <div className="tile" style={{ borderColor: "#94a3b8" }}><div className="tile-value" style={{ color: "#94a3b8" }}>{m.closed}</div><div className="muted">closed</div></div>
        <div className="tile" style={{ borderColor: "#f97316" }}><div className="tile-value" style={{ color: "#f97316" }}>{m.reopened}</div><div className="muted">reopened (not effective)</div></div>
      </div>
      <div className="chart"><canvas ref={canvas} /></div>
    </div>
  );
}

// ---- forms -------------------------------------------------------------------------------------

type Submit<T> = (body: T) => Promise<void>;

function useSubmit<T>(fn: Submit<T>) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = (body: T) => (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    fn(body).catch((err) => setError(String(err))).finally(() => setBusy(false));
  };
  return { error, busy, run };
}

const Err = ({ error }: { error: string | null }) => (error ? <p className="review">{error}</p> : null);

export function IntakeForm({ api, onSubmit }: { api: Backend; onSubmit: Submit<NonconformanceIn> }) {
  const [f, setF] = useState<NonconformanceIn>({ description: "", source: "internal", severity: "major", detected_date: today() });
  const [hint, setHint] = useState<Suggestion | null>(null);
  const { error, busy, run } = useSubmit(onSubmit);
  useEffect(() => {
    // ponytail: setTimeout debounce beats a hook library for one live hint.
    if (!f.description.trim()) return setHint(null);
    const t = setTimeout(() => api.suggest(f.description).then(setHint, () => setHint(null)), 300);
    return () => clearTimeout(t);
  }, [f.description, api]);
  return (
    <form className="intake" onSubmit={run(f)}>
      <h2>New nonconformance <span className="muted small">21 CFR 820.100(a)(1): identify</span></h2>
      <div className="row">
        <textarea required placeholder="What was observed? (e.g. bracket torque out of spec on line 3; work instruction lacks a torque spec)" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        <div className="stack">
          <label>source
            <select value={f.source} onChange={(e) => setF({ ...f, source: e.target.value as NonconformanceIn["source"] })}>
              {["audit", "complaint", "internal", "supplier"].map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label>severity
            <select value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value as NonconformanceIn["severity"] })}>
              {["minor", "major", "critical"].map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label>detected <input type="date" required value={f.detected_date} onChange={(e) => setF({ ...f, detected_date: e.target.value })} /></label>
          <button type="submit" disabled={busy}>Open NC</button>
        </div>
      </div>
      {hint && <SuggestionHint s={hint} />}
      <Err error={error} />
    </form>
  );
}

const SuggestionHint = ({ s }: { s: Suggestion }) => (
  <p className="small">
    category hint: <Chip band={s.band} /> {" "}
    {s.band === "HIGH" && <>looks like <b>{s.suggested}</b> (confidence {s.confidence.toFixed(2)})</>}
    {s.band === "AMBIGUOUS" && <>could be {s.candidates.map(([c, p]) => `${c} (${Math.round(p * 100)}%)`).join(" or ")}</>}
    {s.band === "LOW" && <span className="muted">{s.prompt}</span>}
  </p>
);

export function RcaForm({ api, nc, onSubmit }: { api: Backend; nc: Nonconformance; onSubmit: Submit<Omit<Rca, "confidence_band">> }) {
  const [method, setMethod] = useState<Rca["method"]>("5-why");
  const [answers, setAnswers] = useState<string[]>(["", "", "", "", ""]);
  const [causes, setCauses] = useState<Record<Category, string>>(Object.fromEntries(CATEGORIES.map((c) => [c, ""])) as Record<Category, string>);
  const [rootCause, setRootCause] = useState("");
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [chosen, setChosen] = useState<Category | null>(null);
  const { error, busy, run } = useSubmit(onSubmit);
  useEffect(() => {
    api.suggest(nc.description).then((s) => { setSuggestion(s); setChosen(s.suggested); }, () => setSuggestion(null));
  }, [api, nc.description]);

  // Each question chains off the previous answer, as app/rca.py's next_why_prompt does.
  const questions = answers.map((_, i) => `Why did ${(i === 0 ? nc.description : answers[i - 1] || "…").trim().replace(/\.$/, "")} happen?`);
  const whySteps: WhyStep[] = answers.map((a, i) => ({ question: questions[i], answer: a.trim() })).filter((s) => s.answer);
  const fishSteps: FishboneEntry[] = CATEGORIES.filter((c) => causes[c].trim()).map((c) => ({ category: c, cause: causes[c].trim() }));
  const body: Omit<Rca, "confidence_band"> = {
    nonconformance_id: nc.id,
    method,
    steps: method === "5-why" ? whySteps : fishSteps,
    suggested_category: chosen,
    confidence: suggestion?.confidence ?? null,
    root_cause_text: rootCause,
  };
  return (
    <form onSubmit={run(body)}>
      <h3>Root cause analysis <span className="muted small">820.100(a)(2): investigate</span></h3>
      <div className="radios">
        {(["5-why", "fishbone"] as const).map((m) => (
          <label key={m}><input type="radio" name="method" checked={method === m} onChange={() => setMethod(m)} /> {m}</label>
        ))}
      </div>
      {method === "5-why" ? (
        <ol className="whys">
          {answers.map((a, i) => (
            <li key={i}>
              <div className="muted small">{questions[i]}</div>
              <input placeholder={i === 0 ? "Because…" : "Because… (leave blank to stop the chain)"} value={a} onChange={(e) => setAnswers(answers.map((x, j) => (j === i ? e.target.value : x)))} />
            </li>
          ))}
        </ol>
      ) : (
        <table className="fishbone">
          <tbody>
            {CATEGORIES.map((c) => (
              <tr key={c}><th>{c}</th><td><input placeholder="cause (leave blank if none)" value={causes[c]} onChange={(e) => setCauses({ ...causes, [c]: e.target.value })} /></td></tr>
            ))}
          </tbody>
        </table>
      )}
      {suggestion && (
        <div className="panel">
          <div className="small">Explainer category suggestion <Chip band={suggestion.band} /> <span className="muted">confidence {suggestion.confidence.toFixed(2)}</span></div>
          {suggestion.band === "HIGH" && <p>Auto-suggested <b>{suggestion.suggested}</b>. Advisory only; change it below if the investigation says otherwise.</p>}
          {suggestion.band === "AMBIGUOUS" && (
            <p>Two candidates fit. Pick one: {suggestion.candidates.map(([c, p]) => (
              <button key={c} type="button" className={chosen === c ? "pick active" : "pick"} onClick={() => setChosen(c)}>{c} ({Math.round(p * 100)}%)</button>
            ))}</p>
          )}
          {suggestion.band === "LOW" && <p className="muted">{suggestion.prompt}</p>}
          <label className="small">category (human call)
            <select value={chosen ?? ""} onChange={(e) => setChosen((e.target.value || null) as Category | null)}>
              <option value="">— none —</option>
              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </label>
        </div>
      )}
      <label>root cause (human-entered; the Explainer never fills this)
        <textarea value={rootCause} onChange={(e) => setRootCause(e.target.value)} placeholder="Final quality-engineering call on the root cause" />
      </label>
      <button type="submit" disabled={busy}>Record RCA</button>
      <Err error={error} />
    </form>
  );
}

export function CapaForm({ nc, revised, onSubmit }: { nc: Nonconformance; revised: boolean; onSubmit: Submit<{ nonconformance_id: string; action_description: string; owner: string; due_date: string }> }) {
  const [f, setF] = useState({ nonconformance_id: nc.id, action_description: "", owner: "", due_date: today() });
  const { error, busy, run } = useSubmit(onSubmit);
  return (
    <form onSubmit={run(f)}>
      <h3>{revised ? "Revised corrective action (reopened)" : "Corrective action"} <span className="muted small">820.100(a)(3): action to correct and prevent recurrence</span></h3>
      {revised && <p className="review">The previous verification was not effective; this action replaces the earlier CAPA and re-enters verification.</p>}
      <textarea required placeholder="Action description" value={f.action_description} onChange={(e) => setF({ ...f, action_description: e.target.value })} />
      <div className="row">
        <label>owner <input required value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} /></label>
        <label>due <input type="date" required value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} /></label>
        <button type="submit" disabled={busy}>Assign CAPA</button>
      </div>
      <p className="muted small">An effectiveness check is scheduled automatically at due date + 30 days (CAPA_EFFECTIVENESS_INTERVAL_DAYS).</p>
      <Err error={error} />
    </form>
  );
}

export function CheckForm({ capaId, onSubmit }: { capaId: string; onSubmit: Submit<{ capa_id: string; check_date: string; method: string; result: CheckResult; evidence_uri: string | null }> }) {
  const [f, setF] = useState({ capa_id: capaId, check_date: today(), method: "", result: "effective" as CheckResult, evidence_uri: "" });
  const { error, busy, run } = useSubmit(onSubmit);
  return (
    <form onSubmit={run({ ...f, evidence_uri: f.evidence_uri || null })}>
      <h3>Effectiveness verification <span className="muted small">820.100(a)(4): verify or validate</span></h3>
      <div className="row">
        <label>method <input required value={f.method} onChange={(e) => setF({ ...f, method: e.target.value })} placeholder="e.g. 30-day torque audit" /></label>
        <label>result
          <select value={f.result} onChange={(e) => setF({ ...f, result: e.target.value as CheckResult })}>
            <option value="effective">effective</option>
            <option value="not_effective">not effective (reopens)</option>
          </select>
        </label>
        <label>date <input type="date" required value={f.check_date} onChange={(e) => setF({ ...f, check_date: e.target.value })} /></label>
      </div>
      <label>evidence URI <input value={f.evidence_uri} onChange={(e) => setF({ ...f, evidence_uri: e.target.value })} placeholder="file://audit-2026-10.pdf" /></label>
      <button type="submit" disabled={busy}>Record check</button>
      <Err error={error} />
    </form>
  );
}

export function CloseForm({ capaId, onSubmit }: { capaId: string; onSubmit: Submit<{ capa_id: string; closed_date: string; closed_by: string; linked_requirement_ids: string[] }> }) {
  const [f, setF] = useState({ closed_by: "", reqs: "", closed_date: today() });
  const { error, busy, run } = useSubmit(onSubmit);
  const body = { capa_id: capaId, closed_date: f.closed_date, closed_by: f.closed_by, linked_requirement_ids: f.reqs.split(",").map((s) => s.trim()).filter(Boolean) };
  return (
    <form onSubmit={run(body)}>
      <h3>Close <span className="muted small">820.100(b): document; evidence exported to the traceability hub</span></h3>
      <div className="row">
        <label>closed by <input required value={f.closed_by} onChange={(e) => setF({ ...f, closed_by: e.target.value })} /></label>
        <label>linked requirement ids <input value={f.reqs} onChange={(e) => setF({ ...f, reqs: e.target.value })} placeholder="REQ-7, RC-12" /></label>
        <label>date <input type="date" required value={f.closed_date} onChange={(e) => setF({ ...f, closed_date: e.target.value })} /></label>
        <button type="submit" disabled={busy}>Close NC</button>
      </div>
      <Err error={error} />
    </form>
  );
}

// ---- detail ------------------------------------------------------------------------------------

export function DetailView({ api, d, onBack, refresh }: { api: Backend; d: Detail; onBack: () => void; refresh: () => Promise<void> }) {
  const nc = d.nonconformance;
  const rca = d.rca;
  const latest = d.checks[0] ?? null;
  const after = <T,>(fn: (b: T) => Promise<unknown>) => (b: T) => fn(b).then(refresh);
  const band = rca?.confidence_band ?? (rca?.confidence == null ? null : rca.confidence >= 0.8 ? "HIGH" : rca.confidence >= 0.55 ? "AMBIGUOUS" : "LOW");
  return (
    <section className="detail">
      <button className="link-btn" onClick={onBack}>← board</button>
      <h2><code>{nc.id}</code> <span className="status">{label(nc.status)}</span></h2>
      <p>{nc.description}</p>
      <p className="muted small">{nc.severity} · {nc.source} · detected {nc.detected_date}</p>

      {rca && (
        <div className="block">
          <h3>Root cause analysis <span className="muted small">{rca.method}</span></h3>
          {rca.method === "5-why" ? (
            <ol className="whys">
              {(rca.steps as WhyStep[]).map((s, i) => (
                <li key={i}>
                  <div className="muted small">{s.question}</div>
                  <div>{s.answer} {d.why_flags[i]?.reads_systemic && <span className="flag" title={d.why_flags[i].reason}>reads systemic</span>}</div>
                </li>
              ))}
            </ol>
          ) : (
            <table><tbody>{(rca.steps as FishboneEntry[]).map((s, i) => <tr key={i}><th>{s.category}</th><td>{s.cause}</td></tr>)}</tbody></table>
          )}
          <p className="small">
            suggested category: <b>{rca.suggested_category ?? "none"}</b>{" "}
            {band && <Chip band={band} />}{" "}
            {rca.confidence != null && <span className="muted">confidence {rca.confidence.toFixed(2)}</span>}
            <span className="muted"> · advisory only</span>
          </p>
          <p><span className="muted small">root cause (human): </span>{rca.root_cause_text || <span className="muted">not recorded</span>}</p>
        </div>
      )}

      {d.capa && (
        <div className="block">
          <h3>Corrective action <code>{d.capa.id}</code></h3>
          <p>{d.capa.action_description}</p>
          <p className="muted small">owner {d.capa.owner} · due {d.capa.due_date} · {d.capa.status}</p>
        </div>
      )}

      {d.checks.length > 0 && (
        <div className="block">
          <h3>Effectiveness checks</h3>
          <table>
            <thead><tr><th>date</th><th>method</th><th>result</th><th>evidence</th></tr></thead>
            <tbody>
              {d.checks.map((c, i) => (
                <tr key={i}><td>{c.check_date}</td><td>{c.method}</td><td className={`result-${c.result}`}>{label(c.result)}</td><td className="muted">{c.evidence_uri ?? "—"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {d.closure && (
        <div className="block">
          <h3>Closure</h3>
          <p>closed {d.closure.closed_date} by {d.closure.closed_by} · linked requirements: {d.closure.linked_requirement_ids.join(", ") || "none"}</p>
          {api.base ? (
            <p>
              <a href={`${api.base}/closure/${d.closure.capa_id}/report.pdf`} target="_blank" rel="noreferrer">closure report (PDF)</a>
              {" · "}
              <a href={`${api.base}/closure/${d.closure.capa_id}/evidence.json`} target="_blank" rel="noreferrer">closure evidence (JSON)</a>
            </p>
          ) : (
            <p className="muted small">closure report PDF and evidence JSON are served by the API (not available in demo mode)</p>
          )}
        </div>
      )}

      <div className="block form-block">
        {nc.status === "open" && <RcaForm api={api} nc={nc} onSubmit={after((b) => api.createRca(b))} />}
        {(nc.status === "rca_in_progress" || nc.status === "capa_assigned") && (
          <CapaForm nc={nc} revised={nc.status === "capa_assigned"} onSubmit={after((b) => api.createCapa(b))} />
        )}
        {nc.status === "effectiveness_pending" && d.capa && latest?.result !== "effective" && (
          <CheckForm capaId={d.capa.id} onSubmit={after((b) => api.recordCheck(b))} />
        )}
        {nc.status === "effectiveness_pending" && d.capa && latest?.result === "effective" && (
          <CloseForm capaId={d.capa.id} onSubmit={after((b) => api.close(b))} />
        )}
        {nc.status === "closed" && <p className="muted">Closed. Nothing further to do under 820.100.</p>}
      </div>
    </section>
  );
}
