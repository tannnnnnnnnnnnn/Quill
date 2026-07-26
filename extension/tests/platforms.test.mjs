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
  /* `frames` model same-origin iframes, which is how Zoom's web client ships
     its entire meeting UI. `blindFrames` throw on contentDocument the way a
     cross-origin frame does. */
  constructor({ media = [], controls = [], frames = [], blindFrames = 0 } = {}) {
    this.media = media;
    this.controls = controls;
    this.frames = [
      ...frames.map((doc) => ({ contentDocument: doc })),
      ...Array.from({ length: blindFrames }, () => ({
        get contentDocument() {
          throw new Error("cross-origin");
        }
      }))
    ];
  }

  querySelectorAll(selector) {
    if (selector === "audio, video") return this.media;
    if (selector === "button, [role='button']") return this.controls;
    if (selector === "iframe") return this.frames;
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

  /*
   * Measured on a real Zoom call, 2026-07-26: the web client puts its whole
   * meeting UI in a same-origin iframe. The top document had 86 buttons and no
   * meeting controls; descending into frames found 183 and the leave control.
   * Its label is bare "End" for the host, not "Leave".
   */
  const zoomLikeTab = new FakeRoot({
    controls: [new FakeControl({ label: "Search" })],
    blindFrames: 1,
    frames: [
      new FakeRoot({ controls: [] }),
      new FakeRoot({ controls: [new FakeControl({ label: "End" })] })
    ]
  });
  assert.equal(
    detectInCall("https://app.zoom.us/wc/71587776655/start", zoomLikeTab).active,
    true,
    "Zoom's leave control lives in a same-origin iframe and must be found there"
  );

  assert.equal(
    detectInCall(
      "https://app.zoom.us/wc/71587776655/start",
      new FakeRoot({
        controls: [new FakeControl({ label: "Search" })],
        blindFrames: 2
      })
    ).active,
    false,
    "cross-origin frames must be skipped without throwing, and prove nothing"
  );

  assert.equal(
    detectInCall(
      "https://teams.live.com/v2/?meetingjoin=true",
      new FakeRoot({ controls: [new FakeControl({ label: "Leave" })] })
    ).active,
    true,
    "personal Teams runs on teams.live.com, not teams.microsoft.com"
  );

  console.log(
    "PASS platforms Meet solo=true; pre-join=false; landing=false; stray video=false; call_end icon=true; Zoom/Teams/Webex leave-control=true; their lobbies=false; non-meeting urls=false; zoom-in-iframe=true; cross-origin-frames-skipped; teams.live.com=true"
  );
} finally {
  if (originalHTMLMediaElement === undefined) {
    delete globalThis.HTMLMediaElement;
  } else {
    globalThis.HTMLMediaElement = originalHTMLMediaElement;
  }
}
