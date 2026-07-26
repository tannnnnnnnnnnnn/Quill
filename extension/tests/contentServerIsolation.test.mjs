import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { TranscriptPoller } from "../src/quillClient.js";
import { WorkerQuillClient } from "../src/workerClient.js";

const extensionRoot = path.resolve(import.meta.dirname, "..");
const contentEntry = path.join(extensionRoot, "src/contentMain.js");
const contentModules = new Map();

async function inspectContentModule(filename) {
  const canonical = path.resolve(filename);
  if (contentModules.has(canonical)) return;
  const source = await readFile(canonical, "utf8");
  contentModules.set(canonical, source);

  const imports = source.matchAll(
    /(?:import|export)\s+(?:[\s\S]*?\s+from\s+)?["']([^"']+)["']/g
  );
  for (const match of imports) {
    if (!match[1].startsWith(".")) continue;
    await inspectContentModule(path.resolve(path.dirname(canonical), match[1]));
  }
}

await inspectContentModule(contentEntry);
const contentMain = contentModules.get(contentEntry);

for (const [filename, source] of contentModules) {
  const relative = path.relative(extensionRoot, filename);
  assert.doesNotMatch(
    source,
    /\bnew\s+QuillClient\s*\(/,
    `${relative} must not construct the fetch-backed QuillClient`
  );
  assert.doesNotMatch(
    source,
    /(?:\bfetch\s*\(|\bnew\s+XMLHttpRequest\s*\(|\.sendBeacon\s*\()/,
    `${relative} must not issue direct network requests`
  );
}
assert.match(
  contentMain,
  /new\s+WorkerQuillClient\s*\(/,
  "contentMain.js must use the service-worker transport adapter"
);

const messages = [];
let fetchCalls = 0;
const originalFetch = globalThis.fetch;
globalThis.fetch = async () => {
  fetchCalls += 1;
  throw new Error("content transport attempted a direct fetch");
};

try {
  const client = new WorkerQuillClient({
    async sendMessage(message) {
      messages.push(structuredClone(message));
      if (message.type === "QUILL_TRANSCRIPT") {
        return { cursor: message.cursor, lines: [] };
      }
      return { ok: true, prompt: true, recordingId: "recording-1" };
    }
  });
  const meeting = {
    platform: "google-meet",
    title: "Design sync",
    url: "https://meet.google.com/abc-defg-hij",
    tabId: 7
  };

  await client.transcript(-1);
  await client.meetingDetected(meeting);
  await client.startRecording(meeting);
  await client.stopRecording("recording-1");
  await client.ignoreMeeting(meeting, { automatic: true });

  assert.equal(fetchCalls, 0);
  assert.deepEqual(messages, [
    { type: "QUILL_TRANSCRIPT", cursor: 0 },
    { type: "QUILL_RETRY_DETECTION", meeting },
    { type: "QUILL_START_RECORDING", meeting },
    { type: "QUILL_STOP_RECORDING", recordingId: "recording-1" },
    { type: "QUILL_IGNORE_MEETING", meeting, automatic: true }
  ]);

  const unavailableClient = new WorkerQuillClient({
    async sendMessage() {
      throw new Error("worker unavailable");
    }
  });
  assert.deepEqual(await unavailableClient.transcript(3), {
    ok: false,
    error: "unavailable",
    message: "Quill isn't running"
  });

  const responses = [
    { ok: false, error: "unavailable", message: "Quill isn't running" },
    { cursor: 2, lines: [{ i: 2, speaker: "them", text: "Recovered" }] }
  ];
  const recoveryEvents = [];
  const recoveryPoller = new TranscriptPoller(
    new WorkerQuillClient({
      async sendMessage() {
        return responses.shift();
      }
    }),
    {
      onData() {
        recoveryEvents.push("data");
      },
      onUnavailable() {
        recoveryEvents.push("unavailable");
      },
      onRecovered() {
        recoveryEvents.push("recovered");
      }
    }
  );
  recoveryPoller.active = true;
  recoveryPoller.schedule = () => {};
  await recoveryPoller.poll();
  await recoveryPoller.poll();
  assert.deepEqual(recoveryEvents, ["unavailable", "recovered", "data"]);
} finally {
  globalThis.fetch = originalFetch;
}

console.log(
  "PASS content server isolation direct fetches=0; transcript/start/stop/ignore/retry routed through runtime messages; offline -> recovered callbacks preserved"
);
