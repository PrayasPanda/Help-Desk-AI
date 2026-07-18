import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useEvents } from "../sse";
import { CATEGORIES, PRIORITIES, Ticket } from "../types";

export default function Dashboard() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState("");
  const [q, setQ] = useState("");

  const load = useCallback(() => {
    const params = new URLSearchParams({ limit: "100" });
    if (status) params.set("status", status);
    if (category) params.set("category", category);
    if (priority) params.set("priority", priority);
    if (q) params.set("q", q);
    api<{ data: Ticket[] }>(`/tickets?${params}`)
      .then((r) => setTickets(r.data))
      .catch((e) => setError(e.message));
  }, [status, category, priority, q]);

  useEffect(() => {
    const t = setTimeout(load, q ? 300 : 0); // debounce the search box
    return () => clearTimeout(t);
  }, [load, q]);

  const connected = useEvents((e) => {
    if (e.type === "ticket:created" || e.type === "ticket:resolved") load();
  }, load);

  return (
    <div className="page">
      <div className="page-head">
        <h2>All Tickets</h2>
        {!connected && <span className="badge warn">reconnecting…</span>}
      </div>
      <div className="filters card">
        <input placeholder="Search title…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      {!tickets ? (
        <p className="muted">Loading…</p>
      ) : tickets.length === 0 ? (
        <div className="card empty">No tickets match.</div>
      ) : (
        <div className="ticket-list">
          {tickets.map((t) => (
            <Link to={`/tickets/${t.id}`} key={t.id} className="card ticket-row">
              <div>
                <strong>{t.title}</strong>
                <p className="muted small">
                  #{t.id} · {t.employee.email} · {new Date(t.created_at).toLocaleString()}
                </p>
              </div>
              <div className="tags">
                <span className={`badge cat-${t.category}`}>{t.category}</span>
                <span className={`badge pri-${t.priority}`}>{t.priority}</span>
                <span className={`badge st-${t.status}`}>{t.status}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
