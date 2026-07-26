import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";

import { QuillSurface } from "../src/quillSurface.js";

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.listeners = new Map();
    this.dataset = {};
    this.className = "";
    this.id = "";
    this.disabled = false;
    this.scrollTop = 0;
    this.clientHeight = 300;
    this._textContent = "";
  }

  get textContent() {
    return this._textContent;
  }

  set textContent(value) {
    this._textContent = String(value);
  }

  get scrollHeight() {
    return this.children.length * 80;
  }

  get isConnected() {
    return this === document.documentElement || Boolean(this.parentNode?.isConnected);
  }

  append(...nodes) {
    for (const node of nodes) {
      node.parentNode = this;
      this.children.push(node);
    }
  }

  replaceChildren(...nodes) {
    for (const child of this.children) child.parentNode = null;
    this.children = [];
    this.append(...nodes);
  }

  remove() {
    if (!this.parentNode) return;
    this.parentNode.children = this.parentNode.children.filter(
      (child) => child !== this
    );
    this.parentNode = null;
  }

  attachShadow() {
    const shadow = new FakeElement("shadow-root");
    shadow.parentNode = this;
    return shadow;
  }

  setAttribute(name, value) {
    this[name] = String(value);
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  click() {
    if (this.disabled) return;
    for (const listener of this.listeners.get("click") || []) {
      listener({ preventDefault() {} });
    }
  }

  focus() {}

  matches(selector) {
    if (selector.startsWith(".")) {
      return this.className.split(/\s+/).includes(selector.slice(1));
    }
    const emptyState = selector.match(/^\[data-empty-state="(.+)"\]$/);
    return emptyState ? this.dataset.emptyState === emptyState[1] : false;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const matches = [];
    for (const child of this.children) {
      if (child.matches(selector)) matches.push(child);
      matches.push(...child.querySelectorAll(selector));
    }
    return matches;
  }
}

const extensionRoot = path.resolve(import.meta.dirname, "..");
const harnessHtml = await readFile(
  path.join(extensionRoot, "harness/index.html"),
  "utf8"
);
assert.match(harnessHtml, /<script type="module" src="harness\.js"><\/script>/);

const observed = [];
const elements = new Map();
const documentElement = new FakeElement("html");
for (const [id, tagName] of [
  ["state", "output"],
  ["detected", "button"],
  ["demo", "button"],
  ["reset", "button"]
]) {
  assert.match(harnessHtml, new RegExp(`id="${id}"`));
  const element = new FakeElement(tagName);
  element.id = id;
  if (id === "state") {
    Object.defineProperty(element, "textContent", {
      get() {
        return this._textContent;
      },
      set(value) {
        this._textContent = String(value);
        if (observed.at(-1) !== this._textContent) observed.push(this._textContent);
      }
    });
  }
  elements.set(id, element);
  documentElement.append(element);
}

globalThis.document = {
  documentElement,
  createElement(tagName) {
    return new FakeElement(tagName);
  },
  querySelector(selector) {
    return selector.startsWith("#") ? elements.get(selector.slice(1)) || null : null;
  }
};
globalThis.location = { search: "" };

const nativeSetTimeout = globalThis.setTimeout;
const nativeSetInterval = globalThis.setInterval;
globalThis.setTimeout = (callback, delay, ...args) =>
  nativeSetTimeout(callback, delay * 0.01, ...args);
globalThis.setInterval = (callback, delay, ...args) =>
  nativeSetInterval(callback, delay * 0.01, ...args);

try {
  await import("../harness/harness.js");
  elements.get("demo").click();

  let replacementRejected = false;
  const deadline = Date.now() + 500;
  while (Date.now() < deadline && observed.at(-1) !== "closed") {
    if (
      !replacementRejected &&
      elements.get("state").textContent.startsWith("live panel")
    ) {
      const before = elements.get("state").textContent;
      elements.get("detected").click();
      replacementRejected = elements.get("state").textContent === before;
    }
    await new Promise((resolve) => nativeSetTimeout(resolve, 2));
  }

  assert.deepEqual(observed.slice(0, 3), [
    "idle",
    "detected card",
    "loading panel"
  ]);
  assert.ok(observed.includes("live panel · transcript"));
  assert.equal(observed.at(-1), "closed");
  assert.equal(replacementRejected, true);

  let resolveStart;
  let automaticIgnores = 0;
  const delayedSurface = new QuillSurface({
    assetUrl: "../icons/mark.png",
    autoDismissMs: 20,
    onTakeNotes: () =>
      new Promise((resolve) => {
        resolveStart = resolve;
      }),
    onIgnore({ automatic } = {}) {
      if (automatic) automaticIgnores += 1;
    }
  });
  delayedSurface.showDetected("Google Meet · web");
  delayedSurface.shadow.querySelector(".primary-button").click();
  await new Promise((resolve) => nativeSetTimeout(resolve, 5));
  assert.equal(automaticIgnores, 0);
  assert.equal(delayedSurface.closed, false);
  delayedSurface.close(false);
  resolveStart({ ok: true, startedAt: Date.now() / 1000 });
  await new Promise((resolve) => nativeSetTimeout(resolve, 2));
  assert.equal(delayedSurface.host, null);

  console.log(
    `PASS harness states=${observed.join(" -> ")}; detected replacement rejected=true; delayed start resurrection blocked=true`
  );
} finally {
  globalThis.setTimeout = nativeSetTimeout;
  globalThis.setInterval = nativeSetInterval;
}
