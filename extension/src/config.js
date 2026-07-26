export const DEFAULT_SERVER_URL = "http://127.0.0.1:8787";

export const SITE_DEFINITIONS = Object.freeze({
  googleMeet: { label: "Google Meet", enabled: true },
  zoom: { label: "Zoom", enabled: true },
  microsoftTeams: { label: "Microsoft Teams", enabled: true },
  webex: { label: "Webex", enabled: true }
});

export const DEFAULT_SETTINGS = Object.freeze({
  serverUrl: DEFAULT_SERVER_URL,
  autoPrompt: true,
  sites: Object.freeze(
    Object.fromEntries(
      Object.entries(SITE_DEFINITIONS).map(([key, site]) => [key, site.enabled])
    )
  )
});

function cleanServerUrl(value) {
  const candidate = typeof value === "string" ? value.trim() : "";
  if (!candidate) return DEFAULT_SERVER_URL;

  try {
    const parsed = new URL(candidate);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return DEFAULT_SERVER_URL;
    }
    return parsed.href.replace(/\/+$/, "");
  } catch {
    return DEFAULT_SERVER_URL;
  }
}

export function normalizeSettings(value = {}) {
  const incomingSites =
    value.sites && typeof value.sites === "object" ? value.sites : {};
  const sites = {};

  for (const [key, definition] of Object.entries(SITE_DEFINITIONS)) {
    sites[key] =
      typeof incomingSites[key] === "boolean"
        ? incomingSites[key]
        : definition.enabled;
  }

  return {
    serverUrl: cleanServerUrl(value.serverUrl),
    autoPrompt:
      typeof value.autoPrompt === "boolean"
        ? value.autoPrompt
        : DEFAULT_SETTINGS.autoPrompt,
    sites
  };
}

export async function getSettings() {
  try {
    const stored = await chrome.storage.sync.get([
      "serverUrl",
      "autoPrompt",
      "sites"
    ]);
    return normalizeSettings(stored);
  } catch {
    return normalizeSettings();
  }
}

export async function saveSettings(settings) {
  const normalized = normalizeSettings(settings);
  await chrome.storage.sync.set(normalized);
  return normalized;
}
