import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Ticket } from "../types";

export default function NewTicket() {
  const nav = useNavigate();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [attachment, setAttachment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const t = await api<Ticket>("/tickets", {
        method: "POST",
        body: JSON.stringify({
          title,
          description,
          attachment_filename: attachment || null,
        }),
      });
      nav(`/tickets/${t.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create ticket");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page narrow">
      <h2>New Ticket</h2>
      <form className="card form" onSubmit={submit}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={200}
                 placeholder="e.g. VPN not connecting from home" />
        </label>
        <label>
          Description
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} required minLength={3}
                    rows={6} placeholder="What happened? What did you try?" />
        </label>
        <label>
          Attachment filename <span className="muted">(optional, name only)</span>
          <input value={attachment} onChange={(e) => setAttachment(e.target.value)} placeholder="screenshot.png" />
        </label>
        {error && <p className="error">{error}</p>}
        <button disabled={busy}>{busy ? "Submitting — AI is classifying…" : "Submit ticket"}</button>
        <p className="muted small">On submit, AI suggests a category and priority. An agent can override them later.</p>
      </form>
    </div>
  );
}
