import { getSettings } from "./src/config.js";
import { platformForUrl } from "./src/platforms.js";
import { QuillClient } from "./src/quillClient.js";

const connectionDot = document.querySelector("#connectionDot");
const connectionText = document.querySelector("#connectionText");
const recordingLabel = document.querySelector("#recordingLabel");
const elapsed = document.querySelector("#elapsed");
const offlineMessage = document.querySelector("#offlineMessage");
const recordButton = document.querySelector("#recordButton");
const optionsLink = document.querySelector("#optionsLink");

let client;
let currentStatus = null;
let clockTimer = null;

function elapsedText(startedAt, serverElapsed = 0) {
  const seconds =
    typeof startedAt === "number" && startedAt > 0
      ? Math.max(0, Math.floor(Date.now() / 1000 - startedAt))
      : Math.max(0, Math.floor(serverElapsed || 0));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return hours
    ? `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`
    : `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function updateClock() {
  elapsed.textContent = elapsedText(
    currentStatus?.startedAt,
    currentStatus?.elapsed
  );
}

function renderOffline() {
  connectionDot.dataset.state = "offline";
  connectionText.textContent = "Quill isn't running";
  recordingLabel.textContent = "Unavailable";
  elapsed.textContent = "—";
  offlineMessage.hidden = false;
  recordButton.disabled = true;
}

function renderStatus(health, status) {
  clearInterval(clockTimer);
  clockTimer = null;
  if (health.ok === false || status.ok === false) {
    renderOffline();
    return;
  }

  currentStatus = status;
  connectionDot.dataset.state = "connected";
  connectionText.textContent = `Connected · v${health.version || "unknown"}`;
  offlineMessage.hidden = true;

  if (status.state === "recording") {
    recordingLabel.textContent = "Recording";
    recordButton.textContent = "Stop & process";
    recordButton.dataset.action = "stop";
    recordButton.disabled = !status.recordingId;
    updateClock();
    clockTimer = setInterval(updateClock, 1000);
  } else if (status.state === "processing") {
    recordingLabel.textContent = "Processing";
    elapsed.textContent = "—";
    recordButton.textContent = "Processing…";
    recordButton.dataset.action = "processing";
    recordButton.disabled = true;
  } else {
    recordingLabel.textContent = "Idle";
    elapsed.textContent = "0:00";
    recordButton.textContent = "Start recording";
    recordButton.dataset.action = "start";
    recordButton.disabled = false;
  }
}

async function refresh() {
  const [health, status] = await Promise.all([
    client.health(),
    client.recordingStatus()
  ]);
  renderStatus(health, status);
}

async function activeTabContext() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const platform = platformForUrl(tab?.url || "");
    return {
      platform: platform?.platform || "manual",
      title: tab?.title || "Manual recording",
      url: tab?.url || ""
    };
  } catch {
    return {
      platform: "manual",
      title: "Manual recording",
      url: ""
    };
  }
}

recordButton.addEventListener("click", async () => {
  recordButton.disabled = true;
  if (recordButton.dataset.action === "stop" && currentStatus?.recordingId) {
    await client.stopRecording(currentStatus.recordingId);
  } else if (recordButton.dataset.action === "start") {
    await client.startRecording(await activeTabContext());
  }
  await refresh();
});

optionsLink.addEventListener("click", () => chrome.runtime.openOptionsPage());
window.addEventListener("unload", () => clearInterval(clockTimer));

const settings = await getSettings();
client = new QuillClient({ baseUrl: settings.serverUrl });
await refresh();
