import assert from "node:assert/strict";

import { detectInCall } from "../src/platforms.js";

class FakeControl {
  constructor({ label = "", text = "", tooltip = "", title = "" } = {}) {
    this.textContent = text;
    this.attributes = new Map([
      ["aria-label", label],
      ["data-tooltip", tooltip],
      ["title", title]
    ]);
  }

  getAttribute(name) {
    return this.attributes.get(name) || null;
  }
}

class FakeRoot {
  constructor({ media = [], controls = [] } = {}) {
    this.media = media;
    this.controls = controls;
  }

  querySelectorAll(selector) {
    if (selector === "audio, video") return this.media;
    if (selector === "button, [role='button']") return this.controls;
    return [];
  }
}

function fakeVideo({
  readyState = 0,
  paused = true,
  ended = false,
  srcObject = null
} = {}) {
  return {
    tagName: "VIDEO",
    readyState,
    paused,
    ended,
    srcObject
  };
}

const originalHTMLMediaElement = globalThis.HTMLMediaElement;
globalThis.HTMLMediaElement = { HAVE_CURRENT_DATA: 2 };

try {
  const measuredSoloMeet = new FakeRoot({
    media: [fakeVideo()],
    controls: [
      new FakeControl({ label: "Turn off microphone" }),
      new FakeControl({ label: "Turn on camera" }),
      new FakeControl({ label: "Leave call" })
    ]
  });
  assert.equal(
    detectInCall(
      "https://meet.google.com/dwj-khta-yzt",
      measuredSoloMeet
    ).active,
    true,
    "a joined solo Meet with one inert video must be detected"
  );

  const preJoinMeet = new FakeRoot({
    media: [fakeVideo({ readyState: 4, paused: false })],
    controls: [new FakeControl({ label: "Join now", text: "Join now" })]
  });
  assert.equal(
    detectInCall(
      "https://meet.google.com/dwj-khta-yzt",
      preJoinMeet
    ).active,
    false,
    "Meet pre-join must not be detected without hang-up chrome"
  );

  assert.equal(
    detectInCall(
      "https://meet.google.com/landing",
      new FakeRoot({
        controls: [new FakeControl({ label: "Leave call" })]
      })
    ).active,
    false,
    "Meet landing must not be detected even if unrelated matching text exists"
  );

  const strayAutoplayVideo = new FakeRoot({
    media: [fakeVideo({ readyState: 4, paused: false })]
  });
  assert.equal(
    detectInCall(
      "https://meet.google.com/dwj-khta-yzt",
      strayAutoplayVideo
    ).active,
    false,
    "one autoplaying video without in-call chrome must not be detected"
  );

  assert.equal(
    detectInCall(
      "https://meet.google.com/dwj-khta-yzt",
      new FakeRoot({
        controls: [new FakeControl({ text: "call_end" })]
      })
    ).active,
    true,
    "Meet's locale-independent call_end icon must detect in-call chrome"
  );

  console.log(
    "PASS platforms Meet solo=true; pre-join=false; landing=false; stray video=false; call_end icon=true"
  );
} finally {
  if (originalHTMLMediaElement === undefined) {
    delete globalThis.HTMLMediaElement;
  } else {
    globalThis.HTMLMediaElement = originalHTMLMediaElement;
  }
}
