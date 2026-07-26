const sleep = (delay) => new Promise((resolve) => setTimeout(resolve, delay));

export class MockQuillClient {
  constructor() {
    this.state = "idle";
    this.recordingId = null;
    this.startedAt = null;
    this.pollCount = 0;
    this.lines = [
      {
        i: 1,
        speaker: "them",
        text: "Can you walk us through the rollout plan for phase two?",
        t: 2.1
      },
      {
        i: 2,
        speaker: "me",
        text: "Sure — we start with the pilot group next Monday.",
        t: 4.8
      },
      {
        i: 3,
        speaker: "them",
        text: "And please loop in the design team earlier this time.",
        t: 7.2
      },
      {
        i: 4,
        speaker: "me",
        text: "Noted, I'll send them the charter by Friday.",
        t: 9.4
      }
    ];
  }

  health() {
    return Promise.resolve({ ok: true, version: "0.1.0", state: this.state });
  }

  meetingDetected() {
    return Promise.resolve({ prompt: true });
  }

  ignoreMeeting() {
    return Promise.resolve({ ok: true });
  }

  async startRecording() {
    this.state = "recording";
    this.recordingId = "mock-recording";
    this.startedAt = Date.now() / 1000;
    this.pollCount = 0;
    return {
      ok: true,
      recordingId: this.recordingId,
      startedAt: this.startedAt
    };
  }

  stopRecording() {
    this.state = "processing";
    return Promise.resolve({ ok: true, state: "processing" });
  }

  recordingStatus() {
    return Promise.resolve({
      state: this.state,
      recordingId: this.recordingId,
      startedAt: this.startedAt,
      elapsed: this.startedAt ? Date.now() / 1000 - this.startedAt : 0
    });
  }

  async transcript(cursor = 0) {
    this.pollCount += 1;
    if (this.pollCount === 1) await sleep(1200);
    const next = this.lines.find((line) => line.i > cursor);
    return {
      cursor: next?.i || cursor,
      lines: next ? [next] : []
    };
  }
}
