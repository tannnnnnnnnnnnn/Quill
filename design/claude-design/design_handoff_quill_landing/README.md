# Handoff: Quill Landing Page

## Overview
Marketing landing page for **Quill**, a macOS menu-bar app that detects calls, transcribes
them in real time, and produces a summary with action items. The page's single goal is the
install CTA ("Download for Mac"). It is one scrolling page: nav → hero (with an in-page
product preview) → how-it-works → install CTA → FAQ hover list → footer.

Its defining feature is a **cursor-anchored colour wipe**: a hard-edged vertical band of
Quill blue that is a duplicated, re-themed copy of the page. The band is centred on the
pointer, its width grows with scroll depth, and it reaches full-viewport coverage exactly
as the FAQ section arrives.

## About the Design Files
The files in this bundle are **design references authored in HTML** — a working prototype
of the intended look and behaviour, not production code to lift wholesale. The task is to
**recreate this design inside the target codebase's existing environment** (Next.js, Astro,
Nuxt, plain Vite, etc.) using its established component patterns, styling solution, and
conventions. If no environment exists yet, pick the framework most appropriate for a
marketing site (a static-first framework such as Next.js or Astro is a good default) and
implement it there.

`Quill Landing.dc.html` uses a small in-house component runtime (`support.js`,
`<x-dc>`, `{{ }}` holes, `<sc-for>`). **Do not port that runtime.** Read it as
"template + a class with lifecycle methods and derived values" and translate to the
target framework's idioms — the markup, the inline styles, and the logic in the class are
what matter.

## Fidelity
**High fidelity.** Colours, typography, spacing, easing curves, and interaction timings are
final and are documented exactly below. Recreate the UI pixel-perfectly using the
codebase's existing primitives where they exist. The only intentionally loose area is
responsive behaviour (see Responsive).

---

## Screens / Views

Single page, 6 stacked regions. Page max content width **1120px**, centred, horizontal
padding **40px**. Body background `#dedbd3`, body text `#1c1c1c`.

### 1. Nav
- **Purpose**: brand mark + jump links + a persistent install affordance.
- **Layout**: flex row, `space-between`, `align-items:center`, padding `26px 40px`,
  max-width 1120px centred. Not sticky.
- **Left**: flex row, gap 11px — logo image 30×30 `object-fit:contain` with
  `filter:var(--logo)`; wordmark "Quill" in Newsreader 24px/600, `letter-spacing:-.01em`.
- **Right**: flex row, gap 30px —
  - "How it works" → `#how`, 14.5px, `color:var(--faint)`
  - "FAQ" → `#faq`, 14.5px, `color:var(--faint)`
  - "Install" → `#install`, 14px/500, `background:var(--btn-bg)`,
    `color:var(--btn-fg)`, padding `9px 18px`, radius 10px.

### 2. Hero
- **Purpose**: state the value proposition and drive the download.
- **Layout**: flex column, centred, `text-align:center`, padding `70px 40px 90px`.
- **Eyebrow pill**: inline-flex, gap 8px, `background:var(--pill)`,
  `1px solid var(--line)`, radius 999px, padding `6px 14px`, 13px,
  `color:var(--muted)`, `margin-bottom:34px`. Contains a 7px dot
  (`background:var(--accent)`, `animation:qPulse 2s ease-in-out infinite`) and the text
  `Now on macOS · free while in beta`.
- **H1**: Newsreader 500, **76px**, `line-height:1.02`, `letter-spacing:-.025em`,
  `max-width:820px`, `text-wrap:balance`, margin `0 0 24px`.
  Copy: `Every call, quietly` / `written down for you.` (explicit `<br>`).
- **Sub**: 19px, `line-height:1.55`, `color:var(--muted)`, `max-width:540px`,
  `margin-bottom:40px`, `text-wrap:pretty`. Copy: "Quill lives in your menu bar, detects
  when a call starts, and turns the conversation into clean notes — transcript, summary,
  and action items — without you lifting a finger."
- **CTA block**: flex column, centred, gap 12px.
  - Primary button: inline-flex, gap 10px, `background:var(--btn-bg)`,
    `color:var(--btn-fg)`, 16px/500, padding `15px 26px`, radius 13px,
    `box-shadow:0 12px 30px var(--shadow)`. Leading 17×20 Apple-logo SVG,
    `fill:currentColor`. Label "Download for Mac". Links to `#install`.
  - Meta line: 14px, `color:var(--faint)` — `Free beta · macOS 13+ · no account needed`.
- **Product preview card** (`margin-top:76px`, `max-width:640px`, full width):
  `background:var(--panel)`, `1px solid var(--line)`, radius 22px, padding 22px,
  `box-shadow:0 30px 70px var(--shadow)`.
  - Title row: three 11px traffic-light dots (`#e08b7d`, `#e9c46a`, `#8bb98a`), gap 8px,
    then `margin-left:auto` a recording pill — `background:var(--pill)`,
    `1px solid var(--line)`, radius 9px, padding `5px 11px`, gap 8px: 15px logo at
    `opacity:.82`, a 6px `#ffc46b` dot pulsing (`qPulse 1.8s`), and `14:32` in
    12px/600 monospace.
  - Inner sheet: `background:var(--card)`, `1px solid var(--line)`, radius 14px,
    padding `24px 26px`, `text-align:left`.
    - Section label pattern: 11px/600, `letter-spacing:.08em`, `text-transform:uppercase`,
      `color:var(--faint)`. Used for "Live transcript" and "Action items".
    - Transcript: flex column gap 13px, 14.5px, `line-height:1.5`,
      `color:var(--muted)`; speaker names bold in `var(--accent)`. Third line at
      `opacity:.55` to imply live streaming. Lines: Maya "Let's lock the launch date
      before we wrap." / You "Agreed. I'll send the timeline tonight." / Maya "Perfect,
      and loop in design on the—".
    - Divider: 1px `var(--line)`, margin `20px 0`.
    - Action items: flex column gap 10px, 14.5px. Each row flex gap 11px with a 16×16
      checkbox, radius 5px, `1.5px solid` — `var(--accent)` for the first (done-ish),
      `var(--line)` for the second. Copy: "Send launch timeline tonight",
      "Loop in design team".
- **Entrance animation**: `qFloat` (see Interactions) staggered 0 / .05 / .1 / .15 / .22s.

### 3. How it works — `id="how"`
- **Purpose**: three-beat explanation.
- **Layout**: padding `120px 40px`. Centred header block `margin-bottom:60px`:
  eyebrow 13px/600 `letter-spacing:.1em` uppercase `color:var(--faint)` reading
  "How it works"; H2 Newsreader 500 **44px** `letter-spacing:-.02em` —
  "Three steps, then it disappears."
- **Cards**: `grid-template-columns:repeat(3,1fr)`, gap 24px. Each:
  `background:var(--card)`, `1px solid var(--line)`, radius 16px, padding 32px.
  - Numeral: serif 22px, `color:var(--accent)`, `margin-bottom:18px` — 01 / 02 / 03.
  - Title: 19px/600, `margin-bottom:10px`.
  - Body: 15px, `line-height:1.55`, `color:var(--muted)`.
  - Copy: **Install & forget** — "Drop Quill in your menu bar once. No accounts to wire
    up, no meetings to schedule bots into." · **It hears the call** — "Zoom, Meet, a phone
    on speaker — Quill detects audio, starts recording, and transcribes in real time." ·
    **Notes, ready** — "The moment you hang up, a clean summary with action items is
    waiting. Search it, share it, forget it."

### 4. Install CTA — `id="install"`
- **Layout**: padding `130px 40px`; inner `max-width:720px` centred, `text-align:center`.
- Logo 56×56 `filter:var(--logo)`, `margin-bottom:26px`.
- H2 Newsreader 500 **52px**, `line-height:1.08`, `letter-spacing:-.02em`,
  `text-wrap:balance` — `Get every word,` / `starting with your next call.`
- Body 18px `line-height:1.55` `color:var(--muted)` `max-width:460px` centred,
  `margin-bottom:38px` — "Free while in beta. Runs entirely on your Mac — recordings
  never leave your device unless you choose to sync."
- Button: same pattern as hero but 17px/500, padding `17px 32px`, radius 14px,
  `box-shadow:0 14px 34px var(--shadow)`, 18×21 Apple SVG.
- Spec line below, `margin-top:16px`, 14px `color:var(--faint)` —
  `macOS 13+ · Apple Silicon & Intel · 24 MB`.
- **Note**: both download links are `href="#"` placeholders. Wire to the real installer URL.

### 5. FAQ — `id="faq"`, also carries `data-faq`
Hover-to-reveal list, editorial/technical styling.
- **Layout**: padding `110px 40px 130px`, inner max-width 1120px.
- **Meta header row**: flex, `justify-content:space-between`, `align-items:baseline`,
  monospace 13px, `letter-spacing:.06em`, `color:var(--faint)`, `margin-bottom:44px`.
  Left is static `03  /  QUESTIONS`. Right is live: `04 ENTRIES` when nothing is hovered,
  `ACTIVE  0n / 04` while row *n* is hovered.
- **H2**: Newsreader 500 **56px**, `line-height:1.05`, `letter-spacing:-.025em`,
  `max-width:640px`, `margin-bottom:70px` — "Everything you'd ask before installing."
- **Rows**: each `border-top:1px solid var(--line)`, `cursor:pointer`; a final
  `border-top` div closes the list. Row grid:
  `grid-template-columns:1fr 46px 1.15fr 30px`, gap 30px, `align-items:center`,
  padding `30px 0`.
  1. **Question** — Newsreader 40px, `line-height:1.1`, `letter-spacing:-.02em`,
     `text-align:right`.
  2. **Index badge** — monospace 12px/600, centred, padding `5px 0`,
     `1px solid var(--line)`, radius 4px. Values 01–04.
  3. **Label + answer** — label monospace 12px `letter-spacing:.09em` uppercase
     `color:var(--faint)`; answer 16px `line-height:1.55` `color:var(--muted)`
     `padding-top:10px` `max-width:420px` `text-wrap:pretty`.
  4. **Arrow** — `↗` 20px, right-aligned, `line-height:1`.
- **Content** (question / label / answer):
  1. "Does it record without asking?" / Consent & control / "No. Quill shows a clear
     recording indicator in your menu bar whenever it's listening, and you can pause
     detection any time."
  2. "Where does my data live?" / Privacy / "Everything runs locally on your Mac by
     default. Transcripts and audio never leave your device unless you turn on sync."
  3. "Which calls does it work with?" / Compatibility / "Any audio your Mac can hear —
     Zoom, Google Meet, Teams, FaceTime, or a phone on speaker. No per-app setup."
  4. "Is it really free?" / Pricing / "Yes, free for the duration of the beta. We'll give
     plenty of notice before any pricing changes."

### 6. Footer
- Padding 40px, max-width 1120px, flex `space-between`, `align-items:center`,
  `flex-wrap:wrap`, gap 16px.
- Left: 22px logo at `opacity:.7` + "© 2026 Quill" 14px `color:var(--faint)`.
- Right: flex gap 24px, 14px `color:var(--faint)` — Privacy, Support, Changelog
  (all `href="#"` placeholders).

---

## Interactions & Behavior

### A. Cursor-anchored colour wipe (the signature effect)
Conceptually: the page exists twice. The normal cream page, and a **blue duplicate**
clipped to a vertical band that follows the cursor. Edges are **hard** — no gradient, no
cross-fade, no colour interpolation. Text inside the band is white-on-blue and fully
legible; text outside is ink-on-cream.

**Structure**
- A `position:fixed; inset:0; z-index:60; pointer-events:none; overflow:hidden` overlay.
- Inside it, a **band** div: `position:absolute; top:0; left:0; height:100%;`
  `overflow:hidden; background:#2f43ff`, with an explicit pixel `width` and
  `transform:translate3d(bandLeft,0,0)`.
- Inside the band, a **clone of the entire page content**, marked with the inverted
  palette (see Design Tokens → inverted set), `position:absolute; top:0; left:0`,
  width pinned to the real content's `offsetWidth`, and
  `transform:translate3d(-bandLeft, -scrollY, 0)` so it counter-cancels the band's
  offset and tracks page scroll.

**Performance requirements (learned the hard way — respect these)**
- **Do not animate `clip-path`** on the overlay. It forces a full repaint of the cloned
  page every frame and the effect becomes visibly laggy (multi-second delay). The
  band-`width` + two `translate3d` approach keeps each frame a GPU composite.
- Clone hygiene: strip `box-shadow`, `animation`, and `transition` from every node in
  the clone; strip duplicate `id`s; set `aria-hidden="true"`;
  `will-change:transform`, `backface-visibility:hidden`.
- Write `width` / `transform` only when the value actually changed (cache last values).
- All work happens in one `requestAnimationFrame` loop; `mousemove` / `scroll` listeners
  only record state and are registered `{passive:true}`.

**Motion model** (one rAF loop; constants are final)
- `MINW = 110` — band half-width at the very top of the page.
- `IDLE = 420` ms — stillness before the band retreats.
- Track `cx` (raw pointer x) and `px` (smoothed centre); each frame
  `px += (cx - px) * 0.30`.
- Each frame `w += (goal - w) * 0.18`, where `w` is the current half-width.
- **Fill progress**: `p = clamp(scrollY / end, 0, 1)` where `end` is the scroll offset at
  which the FAQ section is in view —
  `faqTop + faqHeight*0.15 - viewportHeight*0.5`. Query the FAQ node **in the real page
  only** (`[data-content] [data-faq]`); matching the clone's copy produces erratic
  jumping.
- **Target width**: `wTarget = MINW + p^1.7 * need`, where
  `need = max(cx, viewportWidth - cx) + 2`. The `p^1.7` easing keeps it a narrow band
  through most of the page and completes late; scaling by `need` (worst-case distance
  from cursor to either edge) guarantees full coverage at the FAQs regardless of where
  the pointer sits horizontally.
- **Width is owned by scroll position alone.** Moving the cursor *slides* the band; it
  must never widen it, and the band's extremes must never accumulate (min/max history
  was a bug — it grew permanently on every sweep).
- **Idle rule**: if the pointer has been still longer than `IDLE` **and** the page is at
  the very top (progress ≈ 0, i.e. `p^1.7 * need < 2`), `goal = 0` and the band
  disappears. Anywhere else on the page the band holds its scroll-earned width while the
  cursor is still.
- Band geometry each frame: `L = px - w`, `R = px + w`, clamped to
  `[0, viewportWidth]`; band width `= R - L`, band offset `= L`.
- Build the clone ~250ms after mount (lets fonts/layout settle) and rebuild on resize.
- Keep the clone in sync with content changes via a debounced (~200ms) `MutationObserver`
  on the real content — but **ignore mutations originating inside the FAQ section**, and
  re-apply current geometry synchronously after any rebuild. A fresh clone starts 0px
  wide, so an unguarded rebuild flashes the whole viewport back to cream (this was a
  visible glitch when hovering FAQ rows, which mutate the live counter text).
- FAQ hover state is **mirrored** into the clone by copying the row's and answer's
  `style` attributes onto their twins (matched by `data-faq-row`), never by rebuilding.

### B. FAQ hover
- Hovering a row: its answer expands, non-hovered rows dim.
- Answer: `overflow:hidden`, `max-height` 0 → **130px**,
  `opacity` 0 → 1, `transition: max-height .45s cubic-bezier(.2,.8,.2,1), opacity .3s ease`.
- Non-hovered rows: `opacity:.38`, `transition:opacity .35s ease`.
- Meta counter swaps to `ACTIVE  0n / 04`.
- `mouseleave` on the list container resets to no-hover.

### C. Entrance
`@keyframes qFloat { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:none } }`
— `.6s ease both` (`.7s` for the preview card), staggered as noted in Hero.

### D. Ambient
`@keyframes qPulse { 0%,100% { opacity:.35 } 50% { opacity:1 } }` — 2s on the hero pill
dot, 1.8s on the recording dot.

### E. Misc
- `html { scroll-behavior: smooth }`; nav links are in-page anchors.
- Links: `color:var(--accent)`, hover `opacity:.72`.
- Only `img` carries a colour-related transition: `filter .4s linear`.

### Responsive
The prototype is desktop-first and not yet adapted for small screens. Since the wipe is
pointer-driven, **disable the effect on touch/no-hover devices**
(`@media (hover: none)` or `pointer: coarse`) and render only the cream page. Also
respect `prefers-reduced-motion`: skip the wipe and the `qFloat`/`qPulse` animations.
Below ~900px, collapse the how-it-works grid to one column and the FAQ row grid to a
stacked layout (question, then label/answer), and step the display sizes down.

---

## State Management
Minimal — no data fetching, no forms.

**Component state**
- `hov: number` — index of the hovered FAQ row, `-1` for none. Drives row opacity,
  answer expansion, and the meta counter.

**Refs / imperative values (not render state — must not trigger re-render)**
- `cx`, `px` — raw and smoothed pointer x.
- `w`, `wTarget`, `wFloor` — current / target / scroll-earned half-width.
- `last` — timestamp of last pointer or scroll activity (idle test).
- `scrolled` — dirty flag consumed once per frame to re-measure.
- `L`, `R` — current band edges.
- Cached DOM writes: last applied band width, band offset, clone x/y.
- Handles: rAF id, build timeout, MutationObserver.

Everything except `hov` must live outside reactive state, or the per-frame updates will
cause a re-render storm. Clean up rAF, timeout, observer, and all listeners on unmount.

---

## Design Tokens

Implemented as CSS custom properties on the page root, **re-declared** on the blue clone's
root so the same markup renders in either palette. This is the mechanism that keeps text
legible inside the band — swap the whole palette, never blend colours.

### Base (cream)
| Token | Value |
| --- | --- |
| `--paper` (page bg) | `#dedbd3` |
| `--panel` | `#e7e3da` |
| `--card` | `#f4f2ed` |
| `--ink` | `#1c1c1c` |
| `--muted` | `#57534b` |
| `--faint` | `#8a857b` |
| `--accent` | `#4b7bec` |
| `--line` | `rgba(28,28,28,.08)` |
| `--pill` | `rgba(255,255,255,.55)` |
| `--logo` | `brightness(0)` |
| `--btn-bg` | `#1c1c1c` |
| `--btn-fg` | `#f4f2ed` |
| `--shadow` | `rgba(28,28,28,.18)` |

### Inverted (inside the wipe band)
| Token | Value |
| --- | --- |
| `--paper` / `--panel` / band bg | `#2f43ff` |
| `--card` | `rgba(255,255,255,.10)` |
| `--ink` | `#ffffff` |
| `--muted` | `rgba(255,255,255,.86)` |
| `--faint` | `rgba(255,255,255,.66)` |
| `--accent` | `#ffffff` |
| `--line` | `rgba(255,255,255,.28)` |
| `--pill` | `rgba(255,255,255,.14)` |
| `--logo` | `brightness(0) invert(1)` |
| `--btn-bg` | `#ffffff` |
| `--btn-fg` | `#2f43ff` |
| `--shadow` | `rgba(0,0,0,.20)` |

### Fixed accents (identical in both palettes)
Traffic lights `#e08b7d` / `#e9c46a` / `#8bb98a`; recording dot `#ffc46b`.

### Typography
- **Display / headings**: Newsreader (Google Fonts), weights 400/500/600 — variable
  optical size axis `opsz 6..72`. Weight 500 for all headings; 600 for the wordmark.
- **UI / body**: system stack —
  `-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif`,
  with `-webkit-font-smoothing: antialiased`.
- **Mono**: `ui-monospace, "SF Mono", Menlo, monospace`.
- Scale in use: 76 / 56 / 52 / 44 / 40 (display) · 19 / 18 / 17 / 16 / 15 / 14.5 / 14 / 13
  / 12 / 11 (text). Tracking: `-.025em` on the largest display, `-.02em` mid,
  `-.01em` wordmark; `+.06em`–`+.1em` on uppercase mono labels.
- Line heights: 1.02–1.1 display, 1.5–1.55 body.
- `text-wrap: balance` on headings, `text-wrap: pretty` on body paragraphs.

### Spacing
Section padding 110–130px vertical, 40px horizontal. Content max-widths 1120 / 760 / 720 /
640 / 540 / 460 / 420px. Gaps: 6, 8, 10, 11, 12, 13, 16, 24, 30 px. Rhythm steps: 14, 18,
20, 22, 26, 34, 38, 40, 44, 60, 70, 76 px.

### Radius
4 (badge) · 5 (checkbox) · 9 (recording pill) · 10 (nav button) · 13 (row card, hero
button) · 14 (inner sheet, CTA button) · 16 (step card) · 22 (preview card) · 999 (eyebrow
pill).

### Shadow
`0 12px 30px var(--shadow)` (hero button) · `0 14px 34px var(--shadow)` (CTA button) ·
`0 30px 70px var(--shadow)` (preview card).

### Easing / duration
`cubic-bezier(.2,.8,.2,1)` 450ms (answer expand) · `ease` 300/350ms (opacity) ·
`ease` 600/700ms (entrance) · `linear` 400ms (logo filter) · per-frame lerps 0.30
(cursor follow) and 0.18 (width).

---

## Assets
- `assets/quill-logo.png` — the Quill mark, included in this bundle. Rendered as an
  `<img>` recoloured with CSS `filter`: `brightness(0)` for ink-on-cream,
  `brightness(0) invert(1)` for white-on-blue. **Recommendation**: replace with an
  inline SVG using `currentColor` so no filter hack is needed.
- **Apple logo** — inline SVG path in the download buttons (17×20 and 18×21),
  `fill:currentColor`. Ensure use complies with Apple's badge/mark guidelines.
- **Newsreader** — Google Fonts. Self-host in production.
- No photography or illustration; the hero "screenshot" is real DOM, which is what lets it
  invert inside the wipe. Keep it as DOM rather than swapping in an image.

## Screenshots
`screenshots/` captures the effect at successive scroll depths:
- `01-hero-top.png` — top of page, cursor idle, band cleared (cream only).
- `02-wipe-narrow-band.png` — early scroll: narrow cursor-anchored band.
- `03-how-it-works-wipe.png` — band widening across the step cards.
- `04-install-cta-wipe.png` — further growth approaching the CTA.
- `05-faq-full-coverage.png` — full-viewport blue as the FAQs arrive.
- `06-faq-row-hovered.png` — FAQ hover: answer expanded, other rows dimmed.

## Files
- `Quill Landing.dc.html` — the landing page prototype (this handoff's subject).
- `Quill Surfaces.dc.html` — companion exploration of the Quill **app** surfaces
  (menu bar, call popup, live transcript, note card) plus aesthetic-direction variants.
  Context for the product's visual language; not part of the landing page.
- `assets/quill-logo.png` — logo asset.

## Open items for the developer
- Both "Download for Mac" links are `href="#"` — wire to the real installer URL.
- Footer Privacy / Support / Changelog links are placeholders.
- "24 MB", "macOS 13+", "© 2026" are placeholder facts; confirm before launch.
- No analytics, no meta/OG tags, no favicon in the prototype — add per house standards.
- Add the touch / reduced-motion fallbacks described under Responsive.
