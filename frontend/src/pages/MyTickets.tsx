import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useEvents } from "../sse";
import type { Ticket } from "../types";

export default function MyTickets() {
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<{ data: Ticket[] }>("/tickets?limit=100")
      .then((r) => setTickets(r.data))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const connected = useEvents((e) => {
    if (e.type === "ticket:resolved") load();
  }, load);

  if (error) return <p className="error">{error}</p>;
  if (!tickets) return <p className="muted">Loading…</p>;

  return (
    <div className="page">
      <div className="page-head">
        <h2>My Tickets</h2>
        {!connected && <span className="badge warn">reconnecting…</span>}
        <div className="spacer" />
        <Link to="/tickets/new" className="btn-link">+ New Ticket</Link>
      </div>
      {tickets.length === 0 ? (
        <div className="card empty">No tickets yet. Raise your first one!</div>
      ) : (
        <div className="ticket-list">
          {tickets.map((t) => (
            <Link to={`/tickets/${t.id}`} key={t.id} className="card ticket-row">
              <div>
                <strong>{t.title}</strong>
                <p className="muted small">#{t.id} · {new Date(t.created_at).toLocaleString()}</p>
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
