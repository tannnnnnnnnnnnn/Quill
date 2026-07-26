import assert from "node:assert/strict";

const listeners = {
  activated: [],
  installed: [],
  message: [],
  removed: [],
  storageChanged: [],
  updated: []
};
const session = {};
const requests = [];
const requestBodies = [];
let detectedPosts = 0;
let detectedMessages = 0;
let recordingNumber = 0;
const stoppedRecordings = [];
let releaseInitialSessionRead;
const initialSessionRead = new Promise((resolve) => {
  releaseInitialSessionRead = resolve;
});
let delaySessionRead = true;

function event(name) {
  return {
    addListener(listener) {
      listeners[name].push(listener);
    }
  };
}

globalThis.chrome = {
  storage: {
    sync: {
      async get() {
        return {};
      }
    },
    session: {
      async get(keys) {
        if (delaySessionRead) {
          delaySessionRead = false;
          await initialSessionRead;
        }
        return Object.fromEntries(
          keys.filter((key) => key in session).map((key) => [key, session[key]])
        );
      },
      async set(value) {
        Object.assign(session, structuredClone(value));
      }
    },
    onChanged: event("storageChanged")
  },
  tabs: {
    async get(tabId) {
      return {
        id: tabId,
        title: "Design sync",
        url: "https://meet.google.com/abc-defg-hij"
      };
    },
    async query() {
      return [];
    },
    async sendMessage(_tabId, message) {
      if (message.type === "QUILL_SHOW_DETECTED") detectedMessages += 1;
      return { ok: true };
    },
    onActivated: event("activated"),
    onRemoved: event("removed"),
    onUpdated: event("updated")
  },
  runtime: {
    onInstalled: event("installed"),
    onMessage: event("message")
  }
};

globalThis.fetch = async (url, options) => {
  requests.push(url);
  if (options?.body) requestBodies.push(JSON.parse(options.body));
  const path = new URL(url).pathname;
  let payload = { ok: true };
  if (path === "/meeting/detected") {
    detectedPosts += 1;
    await new Promise((resolve) => setTimeout(resolve, 10));
    payload = { prompt: true };
  } else if (path === "/recording/start") {
    recordingNumber += 1;
    payload = {
      ok: true,
      recordingId: `recording-${recordingNumber}`,
      startedAt: recordingNumber
    };
  } else if (path === "/recording/stop") {
    stoppedRecordings.push(JSON.parse(options.body).recordingId);
  } else if (path === "/transcript") {
    payload = {
      cursor: Number(new URL(url).searchParams.get("since")),
      lines: []
    };
  }
  return {
    ok: true,
    async json() {
      return payload;
    }
  };
};

const tab = {
  id: 7,
  title: "Design sync",
  url: "https://meet.google.com/abc-defg-hij"
};
const callState = {
  active: true,
  title: tab.title,
  url: tab.url
};
const meeting = {
  platform: "google-meet",
  context: "Google Meet · web",
  title: tab.title,
  url: tab.url,
  tabId: tab.id
};

function send(listener, message) {
  return new Promise((resolve) => {
    const keepAlive = listener(message, { tab }, resolve);
    assert.equal(
      keepAlive,
      true,
      "supported runtime messages must keep the response channel open"
    );
  });
}

async function waitFor(predicate) {
  const deadline = Date.now() + 500;
  while (!predicate()) {
    assert.ok(Date.now() < deadline, "timed out waiting for background task");
    await new Promise((resolve) => setTimeout(resolve, 2));
  }
}

await import("../background.js?worker=1");
const firstWorker = listeners.message.at(-1);
let earlyMessagesSettled = false;
const earlyMessages = Promise.all([
  send(firstWorker, { type: "QUILL_CALL_STATE", state: callState }),
  send(firstWorker, { type: "QUILL_CALL_STATE", state: callState }),
  send(firstWorker, { type: "QUILL_TRANSCRIPT", cursor: 4 })
]).then(() => {
  earlyMessagesSettled = true;
});
await Promise.resolve();
assert.equal(earlyMessagesSettled, false);
assert.equal(detectedPosts, 0);
releaseInitialSessionRead();
await earlyMessages;
assert.equal(detectedPosts, 1);
assert.equal(detectedMessages, 1);
assert.equal(session.quillTabStates["7"].reportedKey, tab.url);
assert.ok(requests.some((url) => url.endsWith("/transcript?since=4")));

await import("../background.js?worker=2");
const secondWorker = listeners.message.at(-1);
await send(secondWorker, { type: "QUILL_CALL_STATE", state: callState });
assert.equal(detectedPosts, 1);

const started = await send(secondWorker, {
  type: "QUILL_START_RECORDING",
  meeting
});
assert.equal(started.recordingId, "recording-1");
assert.equal(
  session.quillActiveRecordings["7"].recordingId,
  "recording-1"
);
const retried = await send(secondWorker, {
  type: "QUILL_RETRY_DETECTION",
  meeting
});
assert.equal(retried.prompt, true);
await send(secondWorker, {
  type: "QUILL_IGNORE_MEETING",
  meeting,
  automatic: true
});
assert.ok(
  requestBodies.some(
    (body) =>
      body.tabId === tab.id &&
      body.url === meeting.url &&
      body.automatic === true
  )
);

await import("../background.js?worker=3");
listeners.updated.at(-1)(
  tab.id,
  { url: "https://example.com/" },
  { ...tab, url: "https://example.com/" }
);
await waitFor(() => stoppedRecordings.includes("recording-1"));
assert.deepEqual(session.quillActiveRecordings, {});

const thirdWorker = listeners.message.at(-1);
await send(thirdWorker, { type: "QUILL_START_RECORDING", meeting });
listeners.removed.at(-1)(tab.id);
await waitFor(() => stoppedRecordings.includes("recording-2"));
assert.deepEqual(session.quillActiveRecordings, {});
assert.ok(requests.some((url) => url.endsWith("/meeting/tab-clear")));
assert.ok(
  requests.every((url) => url.startsWith("http://127.0.0.1:8787/"))
);
console.log(
  "PASS background pre-init messages (including transcript) queued with synchronous return=true; serialized detection=1; transcript/retry/automatic-ignore proxied; session restart retained state/recording; navigation and tab removal stopped recordings and cleared server tab state"
);
