import { useEffect, useRef } from "react";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

export interface ServerEvent {
  tipo: string;
  [key: string]: unknown;
}

export function useServerEvents(
  onEvent: (event: ServerEvent) => void,
  enabled: boolean,
): void {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled) return;

    let es: EventSource | null = null;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;
    let retryDelay = 2000;
    let stopped = false;

    function connect() {
      es = new EventSource(`${BASE}/events`, { withCredentials: true });

      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as ServerEvent;
          if (data.tipo !== "connected") {
            onEventRef.current(data);
          }
        } catch {
          // ignore malformed events
        }
      };

      es.onerror = () => {
        es?.close();
        es = null;
        if (!stopped) {
          retryTimeout = setTimeout(() => {
            retryDelay = Math.min(retryDelay * 2, 30_000);
            connect();
          }, retryDelay);
        }
      };

      es.onopen = () => {
        retryDelay = 2000;
      };
    }

    connect();

    return () => {
      stopped = true;
      if (retryTimeout) clearTimeout(retryTimeout);
      es?.close();
    };
  }, [enabled]);
}
