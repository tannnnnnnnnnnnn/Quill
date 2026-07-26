import assert from "node:assert/strict";

import { TranscriptPoller } from "../src/quillClient.js";
import { advanceTranscriptIndex } from "../src/quillSurface.js";

const inclusiveLines = [
  { i: 1, speaker: "them", text: "First" },
  { i: 2, speaker: "me", text: "Second" },
  { i: 2, speaker: "me", text: "Second again" },
  { i: 1, speaker: "them", text: "First again" },
  { i: 3, speaker: "them", text: "Third" }
];
let highestRenderedIndex = -1;
const rendered = [];

for (const line of inclusiveLines) {
  const result = advanceTranscriptIndex(line, highestRenderedIndex);
  highestRenderedIndex = result.highestRenderedIndex;
  if (result.append) rendered.push(line.i);
}

assert.deepEqual(rendered, [1, 2, 3]);
assert.equal(highestRenderedIndex, 3);

const requestedCursors = [];
const responses = [
  { cursor: 2, lines: inclusiveLines.slice(0, 2) },
  { cursor: 2, lines: inclusiveLines.slice(1, 3) },
  { cursor: 5, lines: [{ i: 5, speaker: "them", text: "Fifth" }] }
];
const poller = new TranscriptPoller(
  {
    async transcript(cursor) {
      requestedCursors.push(cursor);
      return responses.shift();
    }
  },
  { onData() {} }
);
poller.active = true;
poller.schedule = () => {};

await poller.poll();
await poller.poll();
await poller.poll();

assert.deepEqual(requestedCursors, [0, 2, 2]);
assert.equal(poller.cursor, 5);
console.log(
  "PASS transcript dedup rendered=[1,2,3] highest=3; cursor requests=[0,2,2] final=5"
);
