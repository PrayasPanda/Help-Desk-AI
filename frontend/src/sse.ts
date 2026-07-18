import { useEffect, useRef, useState } from "react";
import { API_BASE, getToken } from "./api";

/** Single SSE subscription. EventSource reconnects automatically on drop;
 *  we surface connection state so the UI can show a "reconnecting" hint
 *  and refetch on every (re)open to catch anything missed while offline. */
export function useEvents(onEvent: (e: { type: string; [k: string]: unknown }) => void, onReconnect?: () => void) {
  const [connected, setConnected] = useState(true);
  const handler = useRef(onEvent);
  handler.current = onEvent;
  const reconnect = useRef(onReconnect);
  reconnect.current = onReconnect;

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const es = new EventSource(`${API_BASE}/events?token=${encodeURIComponent(token)}`);
    es.onopen = () => {
      setConnected(true);
      reconnect.current?.();
    };
    es.onerror = () => setConnected(false);
    es.onmessage = (msg) => handler.current(JSON.parse(msg.data));
    return () => es.close();
  }, []);

  return connected;
}
