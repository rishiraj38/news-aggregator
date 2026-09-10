"use client";

import { useCallback, useEffect, useState } from "react";

type State<T> = { data?: T; error?: string; loading: boolean };

/**
 * Fetch JSON from an admin endpoint, re-fetching when `url` changes or on
 * `reload()`.
 *
 * State is only set after the request resolves, never synchronously in the
 * effect body, which keeps react-hooks/set-state-in-effect satisfied.
 */
export function useAdminJson<T>(url: string) {
  const [state, setState] = useState<State<T>>({ loading: true });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(url, { cache: "no-store" });
        const json = await res.json().catch(() => ({}));
        if (cancelled) return;
        if (!res.ok) {
          setState({
            loading: false,
            error: typeof json?.error === "string" ? json.error : `Request failed (${res.status})`,
          });
          return;
        }
        setState({ loading: false, data: json as T });
      } catch {
        if (!cancelled) setState({ loading: false, error: "Network error — try again." });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [url, nonce]);

  const reload = useCallback(() => {
    setState((s) => ({ ...s, loading: true }));
    setNonce((n) => n + 1);
  }, []);

  return { ...state, reload };
}
