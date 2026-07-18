import { useEffect, useState } from "react";
import { api } from "../api";
import type { Metrics as M } from "../types";

function fmtDuration(seconds: number | null) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

export default function Metrics() {
  const [m, setM] = useState<M | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<M>("/metrics").then(setM).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!m) return <p className="muted">Loading…</p>;

  return (
    <div className="page">
      <h2>Metrics</h2>
      <div className="stat-grid">
        <div className="card stat">
          <span className="stat-num">{m.total_tickets}</span>
          <span className="muted">Total tickets</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{m.by_status.open ?? 0}</span>
          <span className="muted">Open</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{m.by_status.resolved ?? 0}</span>
          <span className="muted">Resolved</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{fmtDuration(m.median_resolution_seconds)}</span>
          <span className="muted">Median resolution time</span>
        </div>
        <div className="card stat">
          <span className="stat-num">{(m.category_override_rate * 100).toFixed(1)}%</span>
          <span className="muted">AI category overridden</span>
        </div>
      </div>
      <div className="card">
        <h3>Tickets by category</h3>
        <table>
          <tbody>
            {Object.entries(m.by_category).map(([cat, n]) => (
              <tr key={cat}>
                <td><span className={`badge cat-${cat}`}>{cat}</span></td>
                <td>{n}</td>
                <td className="bar-cell">
                  <div className="bar" style={{ width: `${(n / Math.max(m.total_tickets, 1)) * 100}%` }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
