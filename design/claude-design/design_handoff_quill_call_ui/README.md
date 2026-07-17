# Handoff: Quill — Call Interface (Classic direction)

## Overview
This package specifies the redesigned floating UI surfaces for **Quill**, the on-device
macOS meeting scribe. It covers the four surfaces the app shows around a call:

1. **Menu bar item** — idle / recording / processing states + the dropdown menu
2. **Call-detected popup** — the "take notes?" card that slides in top-right
3. **Live transcript panel** — the streaming Me/Them transcript that floats at the right edge
4. **Note-ready card** — the post-call "Open note / Delete / keep" card

The direction is **"Classic"**: ink-on-paper, the original brand palette, one blue accent,
and the Quill signature mark used throughout.

## About the Design Files
The bundled file `Quill Surfaces.dc.html` is a **design reference created in HTML** — a
prototype showing the intended look, spacing, and motion. It is **not production code to
copy**. The task is to **recreate these surfaces in Quill's existing environment**: all UI
is **AppKit** (`NSPanel` / `NSButton` / `NSTextField` / `NSTextView` / `NSScrollView`)
driven from Python (PyObjC), and lives in **`quill/panels.py`**. There are no web views —
translate the visual spec below into AppKit layer/color/font/spacing calls.

Open the HTML in a browser to see the surfaces live (it animates: the clock ticks, the
model "loads" then goes live, transcript lines stream in, cards slide in). The finalized
direction is the **top board on the canvas, labelled "4 · Classic — final system."** Boards
below it (Warm, the 2a–2d color iterations, 1a–1c) are earlier explorations — ignore them
for implementation.

## Fidelity
**High-fidelity.** Colors, typography, spacing, radii, and motion are final. Recreate the
surfaces to match, adapting the exact values below to AppKit primitives.

## Important change from the current app
The current panels (`panels.py`) are **dark** (`NSColor.colorWithCalibratedWhite_alpha_(0.11, 0.97)`).
This redesign switches them to **light "paper"** panels. Update the panel background color and
all text/button colors accordingly (see Design Tokens). The panel scaffolding
(`_make_panel`, floating level, collection behavior, rounded corners, movable-by-background,
30s / 60s auto-dismiss timers) stays as-is.

---

## Screens / Views

### 1. Menu bar item
**Purpose:** ambient status in the macOS menu bar; click opens the dropdown.

**Icon (template image):** the Quill signature mark, monochrome + alpha, rendered ~17–18pt.
Use `assets/quill-logo.png` (or the existing `assets/menubar.png`) as a **template image**
(`template=True`) so macOS tints it for light/dark menu bars. Do not bake in a color.

**States (title text shown next to the icon):**
- **idle** — icon only (no title). Reference chip shows the icon + system clock only.
- **recording** — icon + a warm **amber dot** (`#ffc46b`, gentle pulse) + elapsed time in
  **monospaced** digits, e.g. `12:04`. Time format: `M:SS` under an hour, `H:MM:SS` over.
- **processing** — icon + three small animated dots (`…`), color `#9a978f`.

**Dropdown menu** (native `NSMenu`; the mock styles it as a light card for reference):
Order and copy exactly —
1. `Stop & Process`   (right: `⌘S`, dimmed)   — when idle this reads `Start Recording`
2. `recording since 2:02 PM`   (disabled/dim status line, `#9a978f`, 11.5px)
3. — divider —
4. `Open Meeting Notes`
5. `Call Detection`   (right: `On` in accent blue `#4b7bec`)
6. `Hide Live Transcript`   (toggles to `Show Live Transcript`)
7. — divider —
8. `Quit`   (right: `⌘Q`, dimmed)

Hover/highlight on an item: background accent blue `#4b7bec`, text white (native menu
highlight is fine — the color reference is for a custom-drawn menu only).

### 2. Call-detected popup
**Purpose:** ask, once, whether to take notes when a call is detected. Top-right, auto-dismiss 30s.

**Panel:** ~**360 × 112 px**, paper `#f4f2ed`, corner radius **16**, hairline border
`rgba(28,28,28,.07)`, shadow `0 12px 32px rgba(28,28,28,.12)`. Internal padding **17px**.

**Layout (top row):** horizontal, 13px gap, vertically centered —
- **Icon slot:** 42 × 42, radius 12, background `rgba(28,28,28,.05)`, centered logo mark
  (ink) at 26px.
- **Text block:** title **"Call detected"** (15px / 600 / -0.01em, ink `#1c1c1c`); subtitle
  **"Microsoft Teams · web · take notes?"** (12.5px, secondary `#6b6b66`, 2px above-gap).
  The context string ("Microsoft Teams · web") is dynamic — from the detector.

**Buttons row** (16px above, 9px gap):
- **Ignore** — ghost: bg `rgba(28,28,28,.05)`, text ink, height 34, radius 9, padding 0 16,
  13px / 500. Hover bg `rgba(28,28,28,.09)`. Fixed width (hugs content).
- **Take notes** — primary: bg accent `#4b7bec`, text white, height 34, radius 9, 13px / 600,
  **fills remaining width** (this is the emphasized default; bind to Return key). Hover `#3d6bd8`.

### 3. Live transcript panel
**Purpose:** stream Me/Them lines while recording. Right edge, closable, draggable, reopenable.

**Panel:** **340 × ~452 px**, paper `#f4f2ed`, radius 16, same border + shadow as above.
Vertical layout: header / scrolling body / footer.

**Header** (14px 15px 12px padding, bottom hairline `rgba(28,28,28,.07)`, 9px gap, centered):
- Logo mark (ink) 19px, then **"Quill"** in the serif wordmark (15px / 600).
- **Status pill:** rounded 20, bg `rgba(28,28,28,.05)`, 2×8 padding —
  - **loading:** a spinning ring (1.5px, top color `#4b7bec`) + label `loading` (`#9a978f`).
  - **live:** a **blue dot** `#4b7bec` (gentle pulse) + label `live` (`#6b6b66`).
- Spacer, then elapsed **clock** (mono, 11px, `#9a978f`).
- **✕ close button:** 24 × 24, radius 7, bg `rgba(28,28,28,.05)`, glyph `#6b6b66`. Hover
  `rgba(28,28,28,.1)`.

**Body** (flex column, 18px vertical gap, 18px 16px padding, vertical scroll):
- **Empty/loading state:** centered spinner + "loading transcription model…" (`#9a978f`, 12.5px).
- **Transcript lines** — no "Me:/Them:" text prefixes. Instead:
  - **Them:** left-aligned, max-width 90%. Small row: **amber dot** `#ffc46b` (6px) + label
    **THEM** (10.5px / 600 / uppercase / .06em, `#6b6b66`). Text below: 13.5px / line-height
    1.5, ink `#1c1c1c`.
  - **Me:** right-aligned, max-width 90%, text-align right. Row (right-justified): label **ME**
    + **blue dot** `#7db8ff` (6px). Text below: same type, ink.
  - Each new line animates in (see Motion).

**Footer** (11px 15px, top hairline): a 4-bar **waveform** (2.5px bars, 14px tall, accent
`#4b7bec`, staggered bounce) + label "listening · both sides" (`#9a978f`, 11.5px).

> AppKit note: the current panel uses one `NSTextView`. To get per-speaker styling, either
> use `NSAttributedString` runs (color the speaker label, keep body ink) or switch the body
> to a stack of small labeled row views. Alignment (Me right / Them left) needs row views or
> paragraph alignment per run.

### 4. Note-ready card
**Purpose:** after processing, offer to open or delete the note. Top-right, auto-dismiss 60s
(dismiss = **keep**). Same footprint/shell as the call-detected popup.

**Top row:**
- **Icon slot:** 42 × 42, radius 12, background `rgba(75,123,236,.1)`, centered **checkmark**
  SVG in accent `#4b7bec` (stroke 2.4, `M20 6 L 9 17 L 4 12`).
- **Text block:** title **"Note ready"** (15 / 600); subtitle **"Teams call · 32 min · 6 action items"**
  (12.5px, `#6b6b66`, truncate tail). Subtitle is dynamic (note title / stats).

**Buttons row:**
- **Delete** — ghost, secondary text `#6b6b66` (hover → ink `#1c1c1c`), bg `rgba(28,28,28,.05)`
  / hover `.09`. Fixed width. Maps to the `"delete"` action (deletes note, transcript, todos, audio).
- **Open note** — primary blue, fills width, Return key. Maps to `"open"`.
- Below buttons: centered hint **"Keeps automatically if you do nothing"** (11px, `#9a978f`).
  Timeout maps to the `"keep"` action.

---

## Interactions & Behavior
- **Entrance:** cards slide + fade in from the right — translateX(26px)+scale(.97)→0 over
  **~0.55s**, easing `cubic-bezier(.2,.9,.25,1)`. (AppKit: animate panel frame origin.x /
  alpha, or a layer transform.)
- **Live dot / recording dot:** gentle opacity+scale pulse, ~1.6–1.8s loop.
- **Loading spinner:** 0.8s linear rotation.
- **Waveform bars:** scaleY 0.3↔1, ~1s ease-in-out, staggered 0/.15/.3/.45s.
- **New transcript line:** fade + 6px rise over 0.4s.
- **Clock:** ticks every second while recording.
- **Buttons:** hover color changes as specified; primary is bound to Return.
- **Auto-dismiss:** popup 30s → treated as "ignore"; note card 60s → treated as "keep".
- **Close (✕) on live panel:** hides panel, stops transcription loop, flips menu to
  "Show Live Transcript" (existing `_panel_closed` behavior).

## State Management
Existing `panels.py` / `menubar.py` state is unchanged; only visuals change. Relevant state:
- Recording state + elapsed seconds (drives menu title + panel clock).
- `processing` flag (drives the processing menu-bar state).
- Live model readiness → header status pill (loading → live).
- Transcript lines (append, keep last ~60), speaker = `me` / `them`.
- Detector context string (call app + surface) → popup subtitle.
- Note metadata (title, duration, action-item count) → note-card subtitle.
- Callbacks: popup → `record:` / `ignore:` / timeout; note → `open` / `delete` / `keep`.

## Design Tokens
**Colors**
- Ink (primary text): `#1c1c1c`
- Paper (panel bg): `#f4f2ed`
- Secondary text: `#6b6b66`
- Tertiary / hint text: `#9a978f`
- Accent (blue, primary buttons / live / links): `#4b7bec`  · hover `#3d6bd8`
- Speaker "Me": `#7db8ff`
- Speaker "Them" / recording dot: `#ffc46b`
- Ghost button bg: `rgba(28,28,28,.05)` · hover `rgba(28,28,28,.09)`
- Hairline border / dividers: `rgba(28,28,28,.07–.08)`
- Note icon slot bg: `rgba(75,123,236,.1)` · call-icon slot bg: `rgba(28,28,28,.05)`

**Typography**
- UI text: system font (SF Pro / `-apple-system`).
- Wordmark "Quill": serif — `ui-serif, "New York", Georgia` (macOS "New York" / `NSFontDesignSerif`).
- Numerals / clock / shortcuts: monospaced — `ui-monospace, "SF Mono", Menlo`.
- Scale: title 15/600/-0.01em · subtitle 12.5 · transcript body 13.5/1.5 · speaker label
  10.5/600/uppercase/.06em · section eyebrow 11/600/uppercase/.08em · menu item 13 · clock 11–12.

**Radii:** panel/card 16 · button 9 · icon slot 12 · dropdown 11 · dropdown item 7 · status pill 20 · ✕ 7.

**Shadow:** `0 12px 32px rgba(28,28,28,.12)` (cards) · `0 14px 34px rgba(28,28,28,.14)` (dropdown).

**Panel sizes:** call popup ~360×112 · note card ~360×112 (≈128 with hint) · live panel 340×~452.

**Spacing:** panel padding 17 · header padding 14/15/12 · body padding 18/16 · row gaps 9–13 ·
transcript line gap 18.

## Assets
- `assets/quill-logo.png` — the Quill signature mark, cut out to a **transparent background**
  from the provided screenshot (gold on transparent). Rendered **ink** (monochrome black) on
  the light surfaces in this design, and as a **template image** in the menu bar. **Prefer a
  vector (SVG) source if available** for crisp scaling — this PNG is only 80×72. The repo's
  `assets/quill.svg` is an older placeholder feather (not this mark).
- `assets/menubar.png` — existing 44×44 monochrome template menu-bar icon (current mark).
- Checkmark on the note card is a simple stroked SVG (spec above) — draw natively, no asset.

## Files
- `Quill Surfaces.dc.html` — the design reference (open in a browser). Target = top board
  **"4 · Classic — final system."**
- `support.js` — runtime needed to open the HTML locally (do not port; it's the prototype engine).
- `assets/` — logo + menu-bar icon.
- Target source to modify in the real app: `quill/panels.py` (all four surfaces) and
  `quill/menubar.py` (menu wiring, states).
