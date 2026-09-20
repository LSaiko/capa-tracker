import { useCallback, useEffect, useState } from "react";
import { connect, type Backend } from "./api";
import { Board, DetailView, IntakeForm, MetricsPanel } from "./components";
import type { Detail, Metrics, Nonconformance } from "./types";
import "./app.css";

export default function App() {
  const [api, setApi] = useState<Backend | null>(null);
  const [ncs, setNcs] = useState<Nonconformance[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null); // ponytail: no router
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { connect().then(setApi); }, []);

  const refresh = useCallback(async () => {
    if (!api) return;
    try {
      const [list, m] = await Promise.all([api.list(), api.metrics()]);
      setNcs(list);
      setMetrics(m);
      setDetail(selectedId ? await api.detail(selectedId) : null);
    } catch (e) {
      setError(String(e));
    }
  }, [api, selectedId]);

  useEffect(() => { void refresh(); }, [refresh]);

  if (error) return <main><p className="review">Failed to load: {error}</p></main>;
  if (!api || !metrics) return <main><p className="muted">Loading...</p></main>;
  return (
    <main>
      <header>
        <div>
          <h1>capa-tracker</h1>
          <p className="muted">
            The Explainer: structures root cause analysis (5-why, fishbone) and effectiveness reasoning under 21 CFR 820.100; category suggestions are routed by three-band confidence and every root-cause and effectiveness call is a human quality-engineering judgment.
          </p>
        </div>
        <span className="badge">{api.mode === "seed" ? "demo mode — seeded data, changes are not saved" : "advisory only · human decides"}</span>
      </header>

      <MetricsPanel m={metrics} />

      {selectedId && detail ? (
        <DetailView api={api} d={detail} onBack={() => setSelectedId(null)} refresh={refresh} />
      ) : (
        <>
          <IntakeForm api={api} onSubmit={(b) => api.createNc(b).then(() => refresh())} />
          <Board ncs={ncs} onSelect={setSelectedId} />
        </>
      )}
    </main>
  );
}
