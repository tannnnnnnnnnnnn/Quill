import { SURFACE_STYLES } from "./surfaceStyles.js";

// Where to send someone whose Quill app isn't reachable — most often because
// they installed the extension without it.
const SETUP_URL = "https://tannnnnnnnnnnnn.github.io/Quill/";

function formatElapsed(startedAt) {
  const startMs =
    typeof startedAt === "number" && startedAt > 0
      ? startedAt * 1000
      : Date.now();
  const elapsed = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
  const hours = Math.floor(elapsed / 3600);
  const minutes = Math.floor((elapsed % 3600) / 60);
  const seconds = elapsed % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function makeButton(label, className, action) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `action-button ${className}`;
  button.textContent = label;
  button.addEventListener("click", action);
  return button;
}

export function advanceTranscriptIndex(line, highestRenderedIndex) {
  if (!Number.isInteger(line?.i)) {
    return { append: true, highestRenderedIndex };
  }
  if (line.i <= highestRenderedIndex) {
    return { append: false, highestRenderedIndex };
  }
  return { append: true, highestRenderedIndex: line.i };
}

export class QuillSurface {
  constructor({
    mount = document.documentElement,
    assetUrl,
    autoDismissMs = 30000,
    onTakeNotes = async () => ({ ok: false }),
    onIgnore = async () => {},
    onClose = async () => {},
    onRetry = async () => false
  } = {}) {
    this.mount = mount;
    this.assetUrl = assetUrl;
    this.autoDismissMs = autoDismissMs;
    this.onTakeNotes = onTakeNotes;
    this.onIgnore = onIgnore;
    this.onClose = onClose;
    this.onRetry = onRetry;
    this.host = null;
    this.shadow = null;
    this.clockTimer = null;
    this.dismissTimer = null;
    this.startedAt = null;
    this.context = "";
    this.closed = true;
    this.highestRenderedIndex = -1;
  }

  ensureRoot() {
    if (this.host?.isConnected) return;
    this.host = document.createElement("div");
    this.host.id = "quill-extension-surface";
    this.host.setAttribute("aria-live", "polite");
    this.shadow = this.host.attachShadow({ mode: "closed" });
    const style = document.createElement("style");
    style.textContent = SURFACE_STYLES;
    this.shadow.append(style);
    this.mount.append(this.host);
  }

  clearSurface() {
    clearInterval(this.clockTimer);
    clearTimeout(this.dismissTimer);
    this.clockTimer = null;
    this.dismissTimer = null;
    if (!this.shadow) return;
    for (const node of [...this.shadow.children]) {
      if (node.tagName !== "STYLE") node.remove();
    }
  }

  showDetected(context) {
    if (this.shadow?.querySelector(".live-panel")) return false;
    this.ensureRoot();
    this.clearSurface();
    this.context = context || "Browser meeting · web";
    this.closed = false;

    const card = document.createElement("section");
    card.className = "surface detected-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-label", "Call detected");

    const top = document.createElement("div");
    top.className = "detected-top";

    const iconSlot = document.createElement("div");
    iconSlot.className = "icon-slot";
    const icon = document.createElement("img");
    icon.src = this.assetUrl;
    icon.alt = "";
    iconSlot.append(icon);

    const copy = document.createElement("div");
    copy.className = "detected-copy";
    const title = document.createElement("h2");
    title.className = "detected-title";
    title.textContent = "Call detected";
    const subtitle = document.createElement("p");
    subtitle.className = "detected-subtitle";
    subtitle.textContent = `${this.context} · take notes?`;
    copy.append(title, subtitle);
    top.append(iconSlot, copy);

    const actions = document.createElement("div");
    actions.className = "detected-actions";
    const ignore = makeButton("Ignore", "ghost-button", () => {
      this.onIgnore();
      this.close(false);
    });
    const takeNotes = makeButton("Take notes", "primary-button", async () => {
      clearTimeout(this.dismissTimer);
      this.dismissTimer = null;
      ignore.disabled = true;
      takeNotes.disabled = true;
      takeNotes.textContent = "Starting…";
      const result = await this.onTakeNotes();
      if (this.closed || !card.isConnected) return;
      if (result?.ok) {
        this.showPanel({ startedAt: result.startedAt });
      } else {
        this.showUnavailable("Open the Quill app to take notes.");
      }
    });
    actions.append(ignore, takeNotes);
    card.append(top, actions);
    this.shadow.append(card);

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !takeNotes.disabled) {
        event.preventDefault();
        takeNotes.click();
      }
    });
    takeNotes.focus({ preventScroll: true });

    this.dismissTimer = setTimeout(() => {
      this.onIgnore({ automatic: true });
      this.close(false);
    }, this.autoDismissMs);
    return true;
  }

  showUnavailable(detail = "Open the Quill app, then try again.") {
    this.ensureRoot();
    this.clearSurface();
    this.closed = false;

    const card = document.createElement("section");
    card.className = "surface detected-card";
    card.setAttribute("role", "alert");

    const top = document.createElement("div");
    top.className = "detected-top";
    const iconSlot = document.createElement("div");
    iconSlot.className = "icon-slot";
    const icon = document.createElement("img");
    icon.src = this.assetUrl;
    icon.alt = "";
    iconSlot.append(icon);

    const copy = document.createElement("div");
    copy.className = "detected-copy";
    const title = document.createElement("h2");
    title.className = "detected-title";
    title.textContent = "Quill isn't running";
    const subtitle = document.createElement("p");
    subtitle.className = "detected-subtitle";
    subtitle.textContent = detail;
    copy.append(title, subtitle);
    top.append(iconSlot, copy);

    const actions = document.createElement("div");
    actions.className = "detected-actions";
    const dismiss = makeButton("Dismiss", "ghost-button", () => this.close(false));
    const retry = makeButton("Try again", "primary-button", async () => {
      dismiss.disabled = true;
      retry.disabled = true;
      retry.textContent = "Checking…";
      const canPrompt = await this.onRetry();
      if (canPrompt) this.showDetected(this.context);
      else {
        dismiss.disabled = false;
        retry.disabled = false;
        retry.textContent = "Try again";
      }
    });
    /*
     * The extension is a remote control for the Quill app on the user's Mac; on
     * its own it can do nothing. Someone who installed only the extension will
     * land here and has no way to guess that, so send them somewhere useful
     * rather than leaving "Try again" as the only exit.
     */
    const setup = document.createElement("a");
    setup.className = "ghost-button setup-link";
    setup.textContent = "Set up Quill";
    setup.href = SETUP_URL;
    setup.target = "_blank";
    setup.rel = "noreferrer";

    actions.append(setup, dismiss, retry);
    card.append(top, actions);
    this.shadow.append(card);
  }

  showPanel({ startedAt = Date.now() / 1000 } = {}) {
    this.ensureRoot();
    this.clearSurface();
    this.closed = false;
    this.startedAt = startedAt;
    this.highestRenderedIndex = -1;

    const panel = document.createElement("section");
    panel.className = "surface live-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Quill live transcript");

    const header = document.createElement("header");
    header.className = "panel-header";
    const mark = document.createElement("img");
    mark.className = "brand-mark";
    mark.src = this.assetUrl;
    mark.alt = "";
    const wordmark = document.createElement("span");
    wordmark.className = "wordmark";
    wordmark.textContent = "Quill";
    const status = document.createElement("span");
    status.className = "status-pill";
    status.dataset.status = "loading";
    status.innerHTML =
      '<span class="status-indicator" aria-hidden="true"></span><span class="status-label">loading</span>';
    const spacer = document.createElement("span");
    spacer.className = "panel-spacer";
    const clock = document.createElement("time");
    clock.className = "clock";
    clock.textContent = formatElapsed(this.startedAt);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "close-button";
    close.setAttribute("aria-label", "Stop recording and close");
    close.textContent = "×";
    close.addEventListener("click", () => {
      this.onClose();
      this.close(false);
    });
    header.append(mark, wordmark, status, spacer, clock, close);

    const body = document.createElement("main");
    body.className = "transcript-body";
    body.append(this.makeLoadingState());

    const footer = document.createElement("footer");
    footer.className = "panel-footer";
    const waveform = document.createElement("span");
    waveform.className = "waveform";
    waveform.setAttribute("aria-hidden", "true");
    waveform.append(
      document.createElement("span"),
      document.createElement("span"),
      document.createElement("span"),
      document.createElement("span")
    );
    const footerLabel = document.createElement("span");
    footerLabel.textContent = "listening · both sides";
    footer.append(waveform, footerLabel);

    panel.append(header, body, footer);
    this.shadow.append(panel);
    this.clockTimer = setInterval(() => {
      clock.textContent = formatElapsed(this.startedAt);
    }, 1000);
  }

  makeLoadingState() {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.dataset.emptyState = "loading";
    const spinner = document.createElement("span");
    spinner.className = "empty-spinner";
    spinner.setAttribute("aria-hidden", "true");
    const title = document.createElement("span");
    title.className = "empty-title";
    title.textContent = "loading transcription model…";
    empty.append(spinner, title);
    return empty;
  }

  setPanelLive() {
    const status = this.shadow?.querySelector(".status-pill");
    const label = this.shadow?.querySelector(".status-label");
    const body = this.shadow?.querySelector(".transcript-body");
    if (!status || !label || !body) return;
    status.dataset.status = "live";
    label.textContent = "live";
    body.querySelector('[data-empty-state="loading"]')?.remove();
    body.querySelector('[data-empty-state="offline"]')?.remove();
  }

  setPanelUnavailable() {
    const status = this.shadow?.querySelector(".status-pill");
    const label = this.shadow?.querySelector(".status-label");
    const body = this.shadow?.querySelector(".transcript-body");
    if (!status || !label || !body) return;
    status.dataset.status = "offline";
    label.textContent = "offline";
    body.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.dataset.emptyState = "offline";
    const title = document.createElement("span");
    title.className = "empty-title";
    title.textContent = "Quill isn't running";
    const detail = document.createElement("span");
    detail.className = "empty-detail";
    detail.textContent = "Open the Quill menu-bar app. This panel will reconnect automatically.";
    empty.append(title, detail);
    body.append(empty);
  }

  appendTranscript(lines) {
    const body = this.shadow?.querySelector(".transcript-body");
    if (!body || !Array.isArray(lines) || lines.length === 0) return;
    const pinned =
      body.scrollHeight - body.scrollTop - body.clientHeight <= 24;
    body.querySelector(".empty-state")?.remove();

    for (const line of lines) {
      if (
        !line ||
        (line.speaker !== "me" && line.speaker !== "them") ||
        typeof line.text !== "string" ||
        !line.text.trim()
      ) {
        continue;
      }
      const deduped = advanceTranscriptIndex(
        line,
        this.highestRenderedIndex
      );
      if (!deduped.append) continue;
      this.highestRenderedIndex = deduped.highestRenderedIndex;
      const row = document.createElement("article");
      row.className = `transcript-line ${line.speaker}`;
      if (Number.isInteger(line.i)) row.dataset.lineIndex = String(line.i);

      const speaker = document.createElement("div");
      speaker.className = "speaker-row";
      const dot = document.createElement("span");
      dot.className = "speaker-dot";
      dot.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.textContent = line.speaker === "me" ? "ME" : "THEM";
      if (line.speaker === "me") speaker.append(label, dot);
      else speaker.append(dot, label);

      const text = document.createElement("p");
      text.className = "transcript-text";
      text.textContent = line.text.trim();
      row.append(speaker, text);
      body.append(row);
    }

    const transcriptRows = body.querySelectorAll(".transcript-line");
    for (let index = 0; index < transcriptRows.length - 60; index += 1) {
      transcriptRows[index].remove();
    }

    if (pinned) body.scrollTop = body.scrollHeight;
  }

  close(notify = true) {
    if (this.closed) return;
    if (notify) this.onClose();
    this.closed = true;
    this.clearSurface();
    this.host?.remove();
    this.host = null;
    this.shadow = null;
  }

  destroy() {
    this.close(false);
  }
}
