import { TranscriptPoller } from "../src/quillClient.js";
import { QuillSurface } from "../src/quillSurface.js";
import { MockQuillClient } from "./mockQuillClient.js";

const state = document.querySelector("#state");
const detectedButton = document.querySelector("#detected");
const demoButton = document.querySelector("#demo");
const resetButton = document.querySelector("#reset");
const client = new MockQuillClient();
let poller = null;
let recordingId = null;
let demoTimers = [];

function setState(value) {
  state.value = value;
  state.textContent = value;
}

function clearDemoTimers() {
  for (const timer of demoTimers) clearTimeout(timer);
  demoTimers = [];
}

const surface = new QuillSurface({
  assetUrl: "../icons/mark.png",
  autoDismissMs: 30000,
  async onTakeNotes() {
    setState("loading panel");
    const result = await client.startRecording({
      platform: "google-meet",
      title: "Design sync",
      url: "https://meet.google.com/abc-defg-hij"
    });
    recordingId = result.recordingId;
    beginPolling();
    return result;
  },
  async onIgnore() {
    await client.ignoreMeeting(42);
    setState("closed");
  },
  async onClose() {
    poller?.stop();
    poller = null;
    if (recordingId) await client.stopRecording(recordingId);
    recordingId = null;
    setState("closed");
  },
  async onRetry() {
    return (await client.meetingDetected()).prompt;
  }
});

function beginPolling() {
  poller?.stop();
  poller = new TranscriptPoller(client, {
    intervalMs: 700,
    maxIntervalMs: 2800,
    onData(lines) {
      surface.setPanelLive();
      surface.appendTranscript(lines);
      setState(lines.length ? "live panel · transcript" : "live panel");
    },
    onUnavailable() {
      surface.setPanelUnavailable();
      setState("offline panel");
    },
    onRecovered() {
      surface.setPanelLive();
      setState("live panel");
    }
  });
  setTimeout(() => poller?.start(), 0);
}

function showDetected(clearTimers = false) {
  if (surface.showDetected("Google Meet · web")) {
    if (clearTimers) clearDemoTimers();
    setState("detected card");
  }
}

async function showLoadingPanel() {
  setState("loading panel");
  const result = await client.startRecording({
    platform: "google-meet",
    title: "Design sync",
    url: "https://meet.google.com/abc-defg-hij"
  });
  recordingId = result.recordingId;
  surface.showPanel({ startedAt: result.startedAt });
  beginPolling();
}

detectedButton.addEventListener("click", () => showDetected(true));

demoButton.addEventListener("click", () => {
  clearDemoTimers();
  surface.destroy();
  setState("idle");
  demoTimers.push(setTimeout(showDetected, 500));
  demoTimers.push(setTimeout(showLoadingPanel, 1900));
  demoTimers.push(
    setTimeout(() => {
      poller?.stop();
      client.stopRecording(recordingId);
      recordingId = null;
      surface.close(false);
      setState("closed");
    }, 9000)
  );
});

resetButton.addEventListener("click", () => {
  clearDemoTimers();
  poller?.stop();
  poller = null;
  recordingId = null;
  surface.destroy();
  setState("idle");
});

setState("idle");

if (new URLSearchParams(location.search).get("demo") === "1") {
  demoButton.click();
}
