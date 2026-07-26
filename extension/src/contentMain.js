import { detectInCall, platformForUrl } from "./platforms.js";
import { TranscriptPoller } from "./quillClient.js";
import { QuillSurface } from "./quillSurface.js";
import { WorkerQuillClient } from "./workerClient.js";

const client = new WorkerQuillClient();
const platform = platformForUrl(location.href);
let lastMeeting = platform
  ? {
      platform: platform.platform,
      context: platform.context,
      title: document.title || platform.label,
      url: location.href
    }
  : null;
let recordingId = null;
let poller = null;
let stateTimer = null;
let lastStateSignature = "";

const surface = new QuillSurface({
  assetUrl: chrome.runtime.getURL("icons/mark.png"),
  onTakeNotes: startRecording,
  onIgnore: ignoreMeeting,
  onClose: stopRecording,
  onRetry: retryDetection
});

async function startRecording() {
  if (!lastMeeting) return { ok: false };
  const result = await client.startRecording(lastMeeting);
  if (result.ok === false || !result.recordingId) return { ok: false };

  recordingId = result.recordingId;
  poller?.stop();
  poller = new TranscriptPoller(client, {
    onData(lines) {
      surface.setPanelLive();
      surface.appendTranscript(lines);
    },
    onUnavailable() {
      surface.setPanelUnavailable();
    },
    onRecovered() {
      surface.setPanelLive();
    }
  });
  setTimeout(() => poller?.start(0), 0);
  return result;
}

async function stopRecording() {
  poller?.stop();
  poller = null;
  const id = recordingId;
  recordingId = null;
  if (id) await client.stopRecording(id);
}

async function ignoreMeeting({ automatic = false } = {}) {
  if (lastMeeting) {
    await client.ignoreMeeting(lastMeeting, { automatic });
  }
}

async function retryDetection() {
  if (!lastMeeting) return false;
  const result = await client.meetingDetected({
    platform: lastMeeting.platform,
    title: lastMeeting.title,
    url: lastMeeting.url,
    tabId: lastMeeting.tabId
  });
  return result.ok !== false && result.prompt === true;
}

function currentCallState() {
  const detected = detectInCall(location.href, document);
  return {
    active: detected.active,
    platform: detected.platform
      ? {
          id: detected.platform.id,
          platform: detected.platform.platform,
          label: detected.platform.label,
          context: detected.platform.context
        }
      : null,
    title: document.title || detected.platform?.label || "Browser meeting",
    url: location.href
  };
}

function reportCallState(force = false) {
  const state = currentCallState();
  const signature = JSON.stringify([
    state.active,
    state.platform?.id,
    state.title,
    state.url
  ]);
  if (!force && signature === lastStateSignature) return;
  lastStateSignature = signature;
  chrome.runtime.sendMessage({ type: "QUILL_CALL_STATE", state }).catch(() => {});
}

function scheduleStateReport() {
  clearTimeout(stateTimer);
  stateTimer = setTimeout(() => reportCallState(), 450);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "QUILL_CHECK_CALL") {
    sendResponse(currentCallState());
    return false;
  }

  if (message?.type === "QUILL_SHOW_DETECTED") {
    lastMeeting = message.meeting;
    surface.showDetected(message.meeting.context);
    sendResponse({ ok: true });
    return false;
  }

  if (message?.type === "QUILL_SHOW_UNAVAILABLE") {
    lastMeeting = message.meeting;
    surface.context = message.meeting.context;
    surface.showUnavailable("Open the Quill app to take notes.");
    sendResponse({ ok: true });
    return false;
  }

  return false;
});

const observer = new MutationObserver(scheduleStateReport);
observer.observe(document.documentElement, {
  childList: true,
  subtree: true
});
document.addEventListener("play", scheduleStateReport, true);
document.addEventListener("pause", scheduleStateReport, true);
window.addEventListener(
  "pagehide",
  () => {
    poller?.stop();
    if (recordingId) {
      client.stopRecording(recordingId);
    }
  },
  { once: true }
);

reportCallState(true);
setInterval(() => reportCallState(true), 5000);
