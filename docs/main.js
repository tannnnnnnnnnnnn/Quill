// Set this once the Web Store listing is approved; the extension ID appears in
// the listing URL. While it is empty the install buttons point at the repo
// instead, because there is nothing to add to Chrome yet.
const CHROME_STORE_URL = "https://chromewebstore.google.com/detail/quill/mckdigacdodbocengchaeonaamobcnil";
const REPO_URL = "https://github.com/tannnnnnnnnnnnn/Quill";

(() => {
  "use strict";

  const content = document.querySelector("[data-content]");
  const overlay = document.querySelector("[data-overlay]");
  const faq = content.querySelector("[data-faq]");
  const rows = [...content.querySelectorAll("[data-faq-row]")];
  const activeLabel = content.querySelector("[data-active-label]");
  const motionDisabled = matchMedia("(hover: none), (pointer: coarse), (prefers-reduced-motion: reduce)");

  document.querySelectorAll("[data-chrome-link]").forEach((link) => {
    if (CHROME_STORE_URL) {
      link.href = CHROME_STORE_URL;
      return;
    }
    link.href = `${REPO_URL}#install`;
    const label = link.querySelector("[data-chrome-label]");
    if (label) {
      label.textContent = "Install from GitHub";
    }
    link.querySelector(".chrome-mark")?.remove();
  });

  const CONFETTI_COLORS = ["#2f43ff", "#4c7dff", "#e2b93b", "#e46a5a", "#57b26a"];
  function burstConfetti(box) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = box.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    for (let i = 0; i < 14; i++) {
      const bit = document.createElement("span");
      bit.className = "confetti-bit";
      const angle = (Math.PI * 2 * i) / 14 + Math.random() * 0.5;
      const dist = 26 + Math.random() * 34;
      bit.style.cssText = `left:${x}px;top:${y}px;background:${CONFETTI_COLORS[i % CONFETTI_COLORS.length]};--dx:${Math.cos(angle) * dist}px;--dy:${Math.sin(angle) * dist - 14}px;--rot:${Math.random() * 540 - 270}deg`;
      document.body.appendChild(bit);
      bit.addEventListener("animationend", () => bit.remove(), { once: true });
    }
  }

  document.querySelectorAll("[data-action-item]").forEach((item) => {
    const box = item.querySelector(".checkbox");
    item.addEventListener("click", () => {
      const nowChecked = !box.classList.contains("checked");
      box.classList.toggle("checked", nowChecked);
      item.classList.toggle("done", nowChecked);
      if (nowChecked) {
        box.classList.remove("pop");
        void box.offsetWidth;
        box.classList.add("pop");
        burstConfetti(box);
      }
      buildClone();
    });
  });

  let band;
  let inner;
  let rebuildTimer;
  let mutationTimer;
  let observer;
  let raf;
  let cx = null;
  let px = null;
  let w = 0;
  let wTarget = 110;
  let wFloor = 0;
  let last = 0;
  let dirty = true;
  let L;
  let R;
  let lastWidth = -1;
  let lastLeft = -1;
  let lastCloneLeft = -1;
  let lastY = -1;

  const MINW = 110;
  const IDLE = 420;
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function place(left, width, y) {
    if (!band || !inner) return;
    if (width !== lastWidth) {
      lastWidth = width;
      band.style.width = `${width}px`;
    }
    if (left !== lastLeft) {
      lastLeft = left;
      band.style.transform = `translate3d(${left}px,0,0)`;
    }
    if (left !== lastCloneLeft || y !== lastY) {
      lastCloneLeft = left;
      lastY = y;
      inner.style.transform = `translate3d(${-left}px,${-y}px,0)`;
    }
  }

  function mirrorFaq() {
    if (!band) return;
    rows.forEach((row) => {
      const key = row.dataset.faqRow;
      const twin = band.querySelector(`[data-faq-row="${key}"]`);
      if (!twin) return;
      twin.setAttribute("style", row.getAttribute("style") || "");
      const answer = row.querySelector("[data-faq-answer]");
      const twinAnswer = twin.querySelector("[data-faq-answer]");
      if (answer && twinAnswer) twinAnswer.setAttribute("style", answer.getAttribute("style") || "");
    });
    const twinLabel = band.querySelector("[data-active-label]");
    if (twinLabel) twinLabel.textContent = activeLabel.textContent;
  }

  function buildClone() {
    if (motionDisabled.matches) {
      overlay.replaceChildren();
      band = inner = null;
      return;
    }
    const newBand = document.createElement("div");
    newBand.style.cssText = "position:absolute;top:0;left:0;height:100%;width:0;overflow:hidden;will-change:transform,width;background:#2f43ff;backface-visibility:hidden";
    const newInner = content.cloneNode(true);
    newInner.removeAttribute("data-content");
    newInner.setAttribute("data-overlay-inner", "");
    newInner.setAttribute("aria-hidden", "true");
    newInner.querySelectorAll("[id]").forEach((node) => node.removeAttribute("id"));
    newInner.querySelectorAll("*").forEach((node) => {
      node.removeAttribute("tabindex");
      node.style.boxShadow = "none";
      node.style.animation = "none";
      node.style.transition = "none";
    });
    newInner.style.cssText += `;position:absolute;top:0;left:0;width:${content.offsetWidth}px;will-change:transform;backface-visibility:hidden;box-shadow:none;animation:none;transition:none`;
    newBand.appendChild(newInner);
    overlay.replaceChildren(newBand);
    band = newBand;
    inner = newInner;
    lastWidth = lastLeft = lastCloneLeft = lastY = -1;
    mirrorFaq();
    if (L !== undefined && R !== undefined) {
      const left = Math.max(0, Math.round(L));
      const right = Math.min(innerWidth, Math.round(R));
      place(left, Math.max(0, right - left), Math.round(scrollY));
    }
  }

  function measure() {
    const end = Math.max(1, faq.getBoundingClientRect().top + scrollY + faq.offsetHeight * 0.15 - innerHeight * 0.5);
    const p = clamp(scrollY / end, 0, 1);
    const pointerX = cx == null ? innerWidth / 2 : cx;
    const need = Math.max(pointerX, innerWidth - pointerX) + 2;
    const grown = Math.pow(p, 1.7) * need;
    wTarget = MINW + grown;
    wFloor = grown;
  }

  function frame(t) {
    raf = requestAnimationFrame(frame);
    if (motionDisabled.matches) return;
    if (dirty) {
      dirty = false;
      measure();
    }
    if (px == null) {
      if (cx == null) return;
      px = cx;
    }
    const active = t - last < IDLE;
    const goal = wFloor < 2 && !active ? 0 : wTarget;
    px += (cx - px) * 0.30;
    w += (goal - w) * 0.18;
    L = px - w;
    R = px + w;
    const y = Math.round(scrollY);
    if (w < 0.5 && goal === 0) {
      place(0, 0, y);
      return;
    }
    const left = Math.max(0, Math.round(L));
    const right = Math.min(innerWidth, Math.round(R));
    place(left, Math.max(0, right - left), y);
  }

  function setFaqState(index) {
    rows.forEach((row, rowIndex) => {
      const answer = row.querySelector("[data-faq-answer]");
      row.style.cssText = `opacity:${index !== -1 && index !== rowIndex ? 0.38 : 1};transition:opacity .35s ease`;
      answer.style.cssText = `overflow:hidden;max-height:${index === rowIndex ? 130 : 0}px;opacity:${index === rowIndex ? 1 : 0};transition:max-height .45s cubic-bezier(.2,.8,.2,1),opacity .3s ease`;
    });
    activeLabel.textContent = index >= 0 ? `ACTIVE  0${index + 1} / 04` : "04 ENTRIES";
    dirty = true;
    mirrorFaq();
  }

  rows.forEach((row, index) => {
    row.addEventListener("mouseenter", () => setFaqState(index));
    row.addEventListener("focus", () => setFaqState(index));
    row.addEventListener("blur", () => setFaqState(-1));
  });
  content.querySelector(".faq-list").addEventListener("mouseleave", () => setFaqState(-1));

  function onMove(event) {
    cx = event.clientX;
    last = performance.now();
    dirty = true;
  }
  function onScroll() {
    dirty = true;
    last = performance.now();
  }
  function onResize() {
    dirty = true;
    measure();
    buildClone();
  }
  function onMotionChange() {
    if (motionDisabled.matches) overlay.replaceChildren();
    else {
      dirty = true;
      buildClone();
    }
  }

  addEventListener("mousemove", onMove, { passive: true });
  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", onResize, { passive: true });
  motionDisabled.addEventListener("change", onMotionChange);

  rebuildTimer = setTimeout(() => {
    measure();
    buildClone();
    observer = new MutationObserver((mutations) => {
      if (mutations.every((mutation) => {
        const node = mutation.target.nodeType === 1 ? mutation.target : mutation.target.parentElement;
        return node && node.closest("[data-faq]");
      })) return;
      clearTimeout(mutationTimer);
      mutationTimer = setTimeout(() => {
        measure();
        buildClone();
      }, 200);
    });
    observer.observe(content, {subtree: true, childList: true, characterData: true});
  }, 250);
  raf = requestAnimationFrame(frame);

  addEventListener("pagehide", () => {
    clearTimeout(rebuildTimer);
    clearTimeout(mutationTimer);
    observer?.disconnect();
    cancelAnimationFrame(raf);
  }, {once: true});
})();
