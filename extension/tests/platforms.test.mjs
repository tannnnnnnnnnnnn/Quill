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

  /*
   * Zoom, Teams, and Webex: a meeting URL plus a leave control. The pre-join
   * lobby is the case that must stay silent — it shares the URL and offers
   * "Join", never "Leave".
   */
  const MEETING_URLS = [
    ["https://us02web.zoom.us/wc/84512345678/join", "Zoom web client"],
    [
      "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc/0",
      "Teams meetup-join deep link"
    ],
    ["https://teams.cloud.microsoft/v2/?meetingjoin=true", "Teams join handoff"],
    ["https://example.webex.com/meet/tanmay", "Webex personal room"]
  ];

  for (const [url, label] of MEETING_URLS) {
    for (const leaveLabel of [
      "Leave",
      "Leave (Ctrl+Shift+H)",
      "Leave meeting",
      "Hang up",
      "End meeting"
    ]) {
      assert.equal(
        detectInCall(
          url,
          new FakeRoot({ controls: [new FakeControl({ label: leaveLabel })] })
        ).active,
        true,
        `${label} with a "${leaveLabel}" control must be detected`
      );
    }

    const lobby = new FakeRoot({
      media: [fakeVideo({ readyState: 4, paused: false })],
      controls: [
        new FakeControl({ label: "Join now", text: "Join now" }),
        new FakeControl({ label: "Leave feedback" })
      ]
    });
    assert.equal(
      detectInCall(url, lobby).active,
      false,
      `${label} pre-join lobby must not be detected, camera preview and all`
    );
  }

  for (const [url, label] of [
    ["https://zoom.us/download", "Zoom marketing page"],
    ["https://teams.microsoft.com/v2/", "Teams shell with no call"],
    ["https://teams.cloud.microsoft/v2/#/conversations/abc", "Teams chat view"],
    ["https://example.webex.com/", "Webex site root"]
  ]) {
    assert.equal(
      detectInCall(
        url,
        new FakeRoot({ controls: [new FakeControl({ label: "Leave" })] })
      ).active,
      false,
      `${label} must not be detected even with a matching control present`
    );
  }

  console.log(
    "PASS platforms Meet solo=true; pre-join=false; landing=false; stray video=false; call_end icon=true; Zoom/Teams/Webex leave-control=true; their lobbies=false; non-meeting urls=false"
  );
} finally {
  if (originalHTMLMediaElement === undefined) {
    delete globalThis.HTMLMediaElement;
  } else {
    globalThis.HTMLMediaElement = originalHTMLMediaElement;
  }
}
