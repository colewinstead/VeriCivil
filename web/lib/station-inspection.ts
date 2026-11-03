export type StationRequest = { station: number | string; curveIndex: number };

// Keep one worker lookup in flight and only the newest waiting station.
export function createStationInspection<T>(lookup: (request: StationRequest) => Promise<T>,
  update: (value: T) => void, fail: (error: string) => void, pending: (value: boolean) => void) {
  let latest: StationRequest | null = null;
  let revision = 0;
  let running = false;
  let cancelled = false;
  const drain = async () => {
    if (running) return;
    running = true;
    while (latest) {
      const request = latest;
      const current = revision;
      latest = null;
      try {
        const value = await lookup(request);
        if (current === revision) update(value);
      } catch (error) {
        if (current === revision) fail(error instanceof Error ? error.message : String(error));
      }
    }
    running = false;
    if (!cancelled) pending(false);
  };
  return {
    request(request: StationRequest) {
      revision++;
      cancelled = false;
      latest = request;
      fail("");
      pending(true);
      void drain();
    },
    cancel() { revision++; latest = null; cancelled = true; },
  };
}
