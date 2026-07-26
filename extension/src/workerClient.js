function unavailable(error = "unavailable") {
  return {
    ok: false,
    error,
    message: "Quill isn't running"
  };
}

function validObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export class WorkerQuillClient {
  constructor({
    sendMessage = (message) => chrome.runtime.sendMessage(message)
  } = {}) {
    this.sendMessage = sendMessage;
  }

  async request(message) {
    try {
      const result = await this.sendMessage(message);
      return validObject(result) ? result : unavailable("invalid-response");
    } catch {
      return unavailable();
    }
  }

  meetingDetected(meeting) {
    return this.request({
      type: "QUILL_RETRY_DETECTION",
      meeting
    });
  }

  ignoreMeeting(meeting, { automatic = false } = {}) {
    return this.request({
      type: "QUILL_IGNORE_MEETING",
      meeting,
      automatic
    });
  }

  startRecording(meeting) {
    return this.request({
      type: "QUILL_START_RECORDING",
      meeting
    });
  }

  stopRecording(recordingId) {
    return this.request({
      type: "QUILL_STOP_RECORDING",
      recordingId
    });
  }

  transcript(cursor = 0) {
    const safeCursor = Number.isInteger(cursor) && cursor >= 0 ? cursor : 0;
    return this.request({
      type: "QUILL_TRANSCRIPT",
      cursor: safeCursor
    });
  }
}
