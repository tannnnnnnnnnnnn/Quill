const REQUEST_TIMEOUT_MS = 4500;
const POLL_INTERVAL_MS = 1500;
const MAX_POLL_INTERVAL_MS = 12000;

function unavailable(error = "unavailable") {
  return {
    ok: false,
    error,
    message: "Quill isn't running"
  };
}

function validObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export class QuillClient {
  constructor({
    baseUrl = "http://127.0.0.1:8787",
    fetchImpl = globalThis.fetch?.bind(globalThis),
    timeoutMs = REQUEST_TIMEOUT_MS
  } = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.fetchImpl = fetchImpl;
    this.timeoutMs = timeoutMs;
  }

  setBaseUrl(baseUrl) {
    if (typeof baseUrl === "string" && baseUrl.trim()) {
      this.baseUrl = baseUrl.trim().replace(/\/+$/, "");
    }
  }

  async request(path, options = {}) {
    if (!this.fetchImpl) return unavailable();

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        ...options,
        headers: {
          Accept: "application/json",
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...options.headers
        },
        signal: controller.signal
      });

      if (!response.ok) return unavailable(`http-${response.status}`);

      const payload = await response.json();
      if (!validObject(payload)) return unavailable("invalid-response");
      return payload;
    } catch {
      return unavailable();
    } finally {
      clearTimeout(timeout);
    }
  }

  health() {
    return this.request("/health");
  }

  meetingDetected({ platform, title, url, tabId }) {
    return this.request("/meeting/detected", {
      method: "POST",
      body: JSON.stringify({ platform, title, url, tabId })
    });
  }

  ignoreMeeting({ tabId, url, automatic = false }) {
    return this.request("/meeting/ignore", {
      method: "POST",
      body: JSON.stringify({ tabId, url, automatic })
    });
  }

  clearTab(tabId) {
    return this.request("/meeting/tab-clear", {
      method: "POST",
      body: JSON.stringify({ tabId })
    });
  }

  startRecording({ platform, title, url }) {
    return this.request("/recording/start", {
      method: "POST",
      body: JSON.stringify({ platform, title, url })
    });
  }

  stopRecording(recordingId) {
    return this.request("/recording/stop", {
      method: "POST",
      body: JSON.stringify({ recordingId })
    });
  }

  recordingStatus() {
    return this.request("/recording/status");
  }

  transcript(cursor = 0) {
    const safeCursor = Number.isInteger(cursor) && cursor >= 0 ? cursor : 0;
    return this.request(`/transcript?since=${safeCursor}`);
  }
}

export class TranscriptPoller {
  constructor(
    client,
    {
      intervalMs = POLL_INTERVAL_MS,
      maxIntervalMs = MAX_POLL_INTERVAL_MS,
      onData = () => {},
      onUnavailable = () => {},
      onRecovered = () => {}
    } = {}
  ) {
    this.client = client;
    this.intervalMs = intervalMs;
    this.maxIntervalMs = maxIntervalMs;
    this.onData = onData;
    this.onUnavailable = onUnavailable;
    this.onRecovered = onRecovered;
    this.cursor = 0;
    this.failures = 0;
    this.active = false;
    this.timer = null;
    this.requestInFlight = false;
  }

  start(cursor = 0) {
    if (this.active) return;
    this.cursor = Number.isInteger(cursor) && cursor >= 0 ? cursor : 0;
    this.active = true;
    this.schedule(0);
  }

  stop() {
    this.active = false;
    this.requestInFlight = false;
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  schedule(delay) {
    if (!this.active) return;
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = setTimeout(() => this.poll(), delay);
  }

  async poll() {
    if (!this.active || this.requestInFlight) return;
    this.requestInFlight = true;
    const result = await this.client.transcript(this.cursor);
    this.requestInFlight = false;
    if (!this.active) return;

    if (result.ok === false) {
      this.failures += 1;
      if (this.failures === 1) this.onUnavailable(result);
      const delay = Math.min(
        this.intervalMs * 2 ** Math.min(this.failures, 4),
        this.maxIntervalMs
      );
      this.schedule(delay);
      return;
    }

    const wasUnavailable = this.failures > 0;
    this.failures = 0;
    const lines = Array.isArray(result.lines) ? result.lines : [];
    if (Number.isInteger(result.cursor) && result.cursor >= this.cursor) {
      this.cursor = result.cursor;
    }
    if (wasUnavailable) this.onRecovered();
    this.onData(lines, this.cursor);
    this.schedule(this.intervalMs);
  }
}
