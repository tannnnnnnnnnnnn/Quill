import { getSettings } from "./src/config.js";
import { callKey, platformForUrl } from "./src/platforms.js";
import { QuillClient } from "./src/quillClient.js";

const tabStates = new Map();
const evaluateTimers = new Map();
const tabTasks = new Map();
const TAB_STATES_KEY = "quillTabStates";
const ACTIVE_RECORDINGS_KEY = "quillActiveRecordings";
let sessionWrite = Promise.resolve();
const activeRecordings = new Map();
let settings;
let client;

async function init() {
  const [initialSettings, storedSession] = await Promise.all([
    getSettings(),
    chrome.storage.session.get([TAB_STATES_KEY, ACTIVE_RECORDINGS_KEY])
  ]);
  settings = initialSettings;
  client = new QuillClient({ baseUrl: settings.serverUrl });

  for (const [tabId, state] of Object.entries(
    storedSession[TAB_STATES_KEY] || {}
  )) {
    if (Number.isInteger(Number(tabId))) tabStates.set(Number(tabId), state);
  }
  for (const [tabId, recording] of Object.entries(
    storedSession[ACTIVE_RECORDINGS_KEY] || {}
  )) {
    if (Number.isInteger(Number(tabId)) && recording?.recordingId) {
      activeRecordings.set(Number(tabId), recording);
    }
  }
}

const ready = init();

async function persistMap(key, map) {
  await ready;
  const value = Object.fromEntries(map);
  sessionWrite = sessionWrite
    .catch(() => {})
    .then(() => chrome.storage.session.set({ [key]: value }));
  return sessionWrite;
}

async function setTabState(tabId, state) {
  await ready;
  tabStates.set(tabId, state);
  await persistMap(TAB_STATES_KEY, tabStates);
}

async function deleteTabState(tabId) {
  await ready;
  if (!tabStates.delete(tabId)) return;
  await persistMap(TAB_STATES_KEY, tabStates);
}

async function runTabTask(tabId, task) {
  await ready;
  const previous = tabTasks.get(tabId) || Promise.resolve();
  const current = previous
    .catch(() => {})
    .then(task)
    .finally(() => {
      if (tabTasks.get(tabId) === current) tabTasks.delete(tabId);
    });
  tabTasks.set(tabId, current);
  return current;
}

function scheduleEvaluation(tabId, delay = 350) {
  clearTimeout(evaluateTimers.get(tabId));
  evaluateTimers.set(
    tabId,
    setTimeout(() => {
      evaluateTimers.delete(tabId);
      runTabTask(tabId, () => evaluateTab(tabId));
    }, delay)
  );
}

async function evaluateTab(tabId) {
  await ready;
  let tab;
  try {
    tab = await chrome.tabs.get(tabId);
  } catch {
    return;
  }

  const platform = platformForUrl(tab.url || "");
  if (!platform || !settings.sites[platform.id]) {
    await deleteTabState(tabId);
    return;
  }

  try {
    const state = await chrome.tabs.sendMessage(tabId, {
      type: "QUILL_CHECK_CALL"
    });
    await processCallState(tab, state);
  } catch {
    // A content script may not exist yet while the document is navigating.
  }
}

async function processCallState(tab, state) {
  await ready;
  const platform = platformForUrl(state?.url || tab.url || "");
  if (!platform || !settings.sites[platform.id]) return;

  const previous = tabStates.get(tab.id) || {};
  if (!state?.active) {
    const inactiveSince = previous.inactiveSince || Date.now();
    if (Date.now() - inactiveSince > 30000 && previous.reportedKey) {
      await setTabState(tab.id, { inactiveSince });
    } else if (previous.inactiveSince !== inactiveSince) {
      await setTabState(tab.id, { ...previous, inactiveSince });
    }
    return;
  }

  const key = callKey(state.url || tab.url);
  if (previous.reportedKey === key) {
    if (previous.inactiveSince !== null) {
      await setTabState(tab.id, { ...previous, inactiveSince: null });
    }
    return;
  }

  const meeting = {
    platform: platform.platform,
    context: platform.context,
    title: state.title || tab.title || platform.label,
    url: state.url || tab.url,
    tabId: tab.id
  };
  await setTabState(tab.id, { reportedKey: key, inactiveSince: null });

  const result = await client.meetingDetected({
    platform: meeting.platform,
    title: meeting.title,
    url: meeting.url,
    tabId: meeting.tabId
  });

  if (!settings.autoPrompt) return;

  const messageType =
    result.ok === false
      ? "QUILL_SHOW_UNAVAILABLE"
      : result.prompt === true
        ? "QUILL_SHOW_DETECTED"
        : null;
  if (!messageType) return;

  try {
    await chrome.tabs.sendMessage(tab.id, {
      type: messageType,
      meeting
    });
  } catch {
    // The meeting notification is best-effort during page transitions.
  }
}

async function startRecordingForTab(tabId, meeting) {
  await ready;
  const existing = activeRecordings.get(tabId);
  if (existing && callKey(existing.url) === callKey(meeting.url)) {
    return { ok: true, ...existing };
  }
  if (existing) await stopRecordingForTab(tabId);

  const result = await client.startRecording({
    platform: meeting.platform,
    title: meeting.title,
    url: meeting.url
  });
  if (result.ok === false || !result.recordingId) return result;

  activeRecordings.set(tabId, {
    recordingId: result.recordingId,
    startedAt: result.startedAt,
    url: meeting.url
  });
  await persistMap(ACTIVE_RECORDINGS_KEY, activeRecordings);
  return result;
}

async function stopRecordingForTab(tabId, recordingId) {
  await ready;
  const active = activeRecordings.get(tabId);
  if (!active || (recordingId && active.recordingId !== recordingId)) {
    return { ok: true };
  }

  activeRecordings.delete(tabId);
  await persistMap(ACTIVE_RECORDINGS_KEY, activeRecordings);
  return client.stopRecording(active.recordingId);
}

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  await ready;
  if (changeInfo.url) {
    runTabTask(tabId, async () => {
      const active = activeRecordings.get(tabId);
      if (active && callKey(active.url) !== callKey(changeInfo.url)) {
        await stopRecordingForTab(tabId);
      }
      await client.clearTab(tabId);
      await deleteTabState(tabId);
    });
  }
  if (
    changeInfo.url ||
    changeInfo.status === "complete" ||
    typeof changeInfo.title === "string"
  ) {
    if (platformForUrl(tab.url || changeInfo.url || "")) {
      scheduleEvaluation(tabId);
    }
  }
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  await ready;
  scheduleEvaluation(tabId, 0);
});

chrome.tabs.onRemoved.addListener(async (tabId) => {
  await ready;
  clearTimeout(evaluateTimers.get(tabId));
  evaluateTimers.delete(tabId);
  runTabTask(tabId, async () => {
    await stopRecordingForTab(tabId);
    await client.clearTab(tabId);
    await deleteTabState(tabId);
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!sender.tab) return false;

  let task;
  if (message?.type === "QUILL_CALL_STATE") {
    task = () => processCallState(sender.tab, message.state);
  } else if (message?.type === "QUILL_START_RECORDING") {
    task = () => startRecordingForTab(sender.tab.id, message.meeting);
  } else if (message?.type === "QUILL_STOP_RECORDING") {
    task = () => stopRecordingForTab(sender.tab.id, message.recordingId);
  } else if (message?.type === "QUILL_IGNORE_MEETING") {
    task = async () => {
      const key = callKey(message.meeting.url);
      const previous = tabStates.get(sender.tab.id) || {};
      await setTabState(sender.tab.id, {
        ...previous,
        reportedKey: key,
        ignoredKey: key
      });
      return client.ignoreMeeting({
        tabId: sender.tab.id,
        url: message.meeting.url,
        automatic: message.automatic === true
      });
    };
  } else if (message?.type === "QUILL_RETRY_DETECTION") {
    task = () =>
      client.meetingDetected({
        platform: message.meeting.platform,
        title: message.meeting.title,
        url: message.meeting.url,
        tabId: sender.tab.id
      });
  } else if (message?.type === "QUILL_TRANSCRIPT") {
    task = () => client.transcript(message.cursor);
  } else {
    return false;
  }

  handleMessage(sender.tab.id, task).then(sendResponse, () => {
    sendResponse({ ok: false, error: "unavailable" });
  });
  // Keep the response channel open synchronously while initialization and the
  // per-tab task finish.
  return true;
});

async function handleMessage(tabId, task) {
  await ready;
  return runTabTask(tabId, task);
}

chrome.storage.onChanged.addListener(async (_changes, area) => {
  if (area !== "sync") return;
  await ready;
  settings = await getSettings();
  client.setBaseUrl(settings.serverUrl);
});

chrome.runtime.onInstalled.addListener(async () => {
  await ready;
  const tabs = await chrome.tabs.query({});
  for (const tab of tabs) {
    if (platformForUrl(tab.url || "")) scheduleEvaluation(tab.id, 0);
  }
});
