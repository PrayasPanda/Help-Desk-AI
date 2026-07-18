import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { CATEGORIES, PRIORITIES, TicketDetail as TD } from "../types";

export default function TicketDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const isAgent = user?.role === "agent";
  const [ticket, setTicket] = useState<TD | null>(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [aiDraft, setAiDraft] = useState("");
  const [citations, setCitations] = useState<string[]>([]);
  const [drafting, setDrafting] = useState(false);
  const [sending, setSending] = useState(false);

  const load = useCallback(() => {
    api<TD>(`/tickets/${id}`).then(setTicket).catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);

  async function override(field: "category" | "priority", value: string) {
    if (!ticket) return;
    try {
      await api(`/tickets/${ticket.id}/classification`, {
        method: "PATCH",
        body: JSON.stringify({ [field]: value }),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Override failed");
    }
  }

  async function generateDraft() {
    if (!ticket) return;
    setDrafting(true);
    setError("");
    try {
      const r = await api<{ draft: string; citations: string[] }>(
        `/tickets/${ticket.id}/draft-reply`, { method: "POST" });
      setAiDraft(r.draft);
      setDraft(r.draft);
      setCitations(r.citations);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Draft generation failed");
    } finally {
      setDrafting(false);
    }
  }

  async function sendReply() {
    if (!ticket || !draft.trim()) return;
    setSending(true);
    setError("");
    try {
      await api(`/tickets/${ticket.id}/reply`, {
        method: "POST",
        body: JSON.stringify({ ai_draft: aiDraft, final_reply: draft, citations }),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSending(false);
    }
  }

  if (error && !ticket) return <p className="error">{error}</p>;
  if (!ticket) return <p className="muted">Loading…</p>;

  return (
    <div className="page narrow">
      <div className="page-head">
        <h2>#{ticket.id} — {ticket.title}</h2>
        <span className={`badge st-${ticket.status}`}>{ticket.status}</span>
      </div>

      <div className="card">
        <p className="muted small">
          Raised by {ticket.employee.email} · {new Date(ticket.created_at).toLocaleString()}
          {ticket.attachment_filename && <> · 📎 {ticket.attachment_filename}</>}
        </p>
        <p className="pre">{ticket.description}</p>
      </div>

      <div className="card">
        <h3>Classification <span className="badge ai">AI-suggested</span></h3>
        <p className="muted small">
          AI suggested: {ticket.ai_category} / {ticket.ai_priority}
          {ticket.ai_confidence != null && <> · confidence {(ticket.ai_confidence * 100).toFixed(0)}%</>}
        </p>
        <div className="row">
          <label>
            Category
            {isAgent ? (
              <select value={ticket.category} onChange={(e) => override("category", e.target.value)}>
                {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            ) : (
              <span className={`badge cat-${ticket.category}`}>{ticket.category}</span>
            )}
          </label>
          <label>
            Priority
            {isAgent ? (
              <select value={ticket.priority} onChange={(e) => override("priority", e.target.value)}>
                {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
              </select>
            ) : (
              <span className={`badge pri-${ticket.priority}`}>{ticket.priority}</span>
            )}
          </label>
        </div>
      </div>

      {ticket.reply ? (
        <div className="card">
          <h3>Reply <span className="muted small">sent {new Date(ticket.reply.sent_at).toLocaleString()}</span></h3>
          <p className="pre">{ticket.reply.final_reply}</p>
          {ticket.reply.citations.length > 0 && (
            <p className="muted small">Sources: {ticket.reply.citations.join(" · ")}</p>
          )}
          {isAgent && ticket.reply.final_reply !== ticket.reply.ai_draft && (
            <details>
              <summary className="muted small">Original AI draft (edited before sending)</summary>
              <p className="pre muted">{ticket.reply.ai_draft}</p>
            </details>
          )}
        </div>
      ) : isAgent ? (
        <div className="card">
          <h3>Reply</h3>
          {!aiDraft && (
            <button onClick={generateDraft} disabled={drafting}>
              {drafting ? "Retrieving KB & drafting…" : "✨ Generate AI draft"}
            </button>
          )}
          {aiDraft && (
            <>
              {citations.length > 0 ? (
                <p className="muted small">📚 Grounded in: {citations.join(" · ")}</p>
              ) : (
                <p className="muted small">⚠️ No relevant KB article found — draft says so.</p>
              )}
              <textarea rows={10} value={draft} onChange={(e) => setDraft(e.target.value)} />
              <div className="row">
                <button onClick={sendReply} disabled={sending || !draft.trim()}>
                  {sending ? "Sending…" : "Send Reply (resolves ticket)"}
                </button>
                <button className="ghost" onClick={generateDraft} disabled={drafting}>
                  {drafting ? "…" : "Regenerate draft"}
                </button>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="card empty">An agent will reply soon.</div>
      )}

      {isAgent && ticket.audit_log.length > 0 && (
        <div className="card">
          <h3>Override audit log</h3>
          <table>
            <thead>
              <tr><th>When</th><th>Agent</th><th>Field</th><th>From</th><th>To</th></tr>
            </thead>
            <tbody>
              {ticket.audit_log.map((a) => (
                <tr key={a.id}>
                  <td>{new Date(a.created_at).toLocaleString()}</td>
                  <td>{a.agent.email}</td>
                  <td>{a.field}</td>
                  <td>{a.old_value}</td>
                  <td>{a.new_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
