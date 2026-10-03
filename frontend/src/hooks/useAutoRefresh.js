import { useEffect, useRef } from 'react';

/**
 * Re-run `refresh` when the browser tab becomes visible / focused,
 * and optionally on a polling interval while the tab is in the foreground.
 */
export function useAutoRefresh(refresh, options = {}) {
  const {
    enabled = true,
    intervalMs = 15000,
    minIntervalMs = 2500,
  } = options;

  const refreshRef = useRef(refresh);
  refreshRef.current = refresh;
  const lastRunRef = useRef(0);
  const inFlightRef = useRef(false);

  useEffect(() => {
    if (!enabled) return undefined;

    const run = async () => {
      if (inFlightRef.current) return;
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastRunRef.current < minIntervalMs) return;
      inFlightRef.current = true;
      lastRunRef.current = now;
      try {
        await refreshRef.current();
      } catch {
        // Page-level loaders already surface errors.
      } finally {
        inFlightRef.current = false;
      }
    };

    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        run();
      }
    };

    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('focus', onVisible);

    const timer = intervalMs > 0
      ? setInterval(run, intervalMs)
      : null;

    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('focus', onVisible);
      if (timer) clearInterval(timer);
    };
  }, [enabled, intervalMs, minIntervalMs]);
}
