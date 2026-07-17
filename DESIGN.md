# Quill — Design Brief

## One-liner

Quill is a private, on-device meeting scribe for macOS. It notices when a call
starts, records both sides without joining as a bot, transcribes locally,
and turns every call into a clean note, a to-do list, and long-term memory —
all stored as plain markdown the user owns.

## Story & positioning

Built as a personal replacement for Granola.ai ($18/mo, cloud). Quill is
$0 and local: audio never leaves the laptop; transcription runs on the M4's
neural silicon; summarization runs through the user's existing Claude
subscription. The tagline space: "taken down by Quill", "your meetings,
minuted", "the quiet scribe in your menu bar".

Personality: **a quiet professional** — invisible until a call starts, one
polite question, then out of the way. Never gamified, never chatty. Think
fountain-pen stationery meets modern macOS: warm ink tones on paper neutrals,
or monochrome with one accent.

## Name & mark

- Name: **Quill**
- Emoji stand-in currently used: 🪶
- Current menu bar icon: SF Symbol "signature" rendered as a template
  (monochrome) PNG — a quill-drawn flourish. See `assets/menubar.png`.
- Logo seed: `assets/quill.svg` — a single-stroke feather with a nib tick.
  **Design ask #1: a real mark.** Directions worth exploring: feather whose
  shaft is a soundwave; feather nib leaving a line that becomes a waveform;
  minimal "Q" whose tail is a quill.

## What it does (the pipeline)

```
detect call ──▶ popup card ──▶ record ──▶ live transcript ──▶ stop
                                  │                             │
                            them.caf + me.caf            transcribe (local)
                                                                │
                                              Claude: note · TODO · people · memory
                                                                │
                                                     Obsidian vault "AI Brain"
```

1. **Detect** — menu bar agent polls every 3s: is the mic live AND a meeting
   present (native app: Teams/Zoom/FaceTime/Webex/Slack/Discord, or a Chrome
   tab on teams.cloud.microsoft / meet.google.com / zoom web)?
2. **Ask** — floating card, top-right: "🪶 Call detected — Teams (web) — take
   notes?" [Ignore] [Take notes]. Auto-dismisses in 30s.
3. **Record** — Audiocap.app captures system audio (them) + microphone (me)
   as two synced tracks. No bot joins the call; works with any call app.
4. **Live** — floating right-edge panel streams "Me: …" / "Them: …" lines
   within ~5s of speech. Closable (✕), reopenable from the menu, draggable.
5. **Process** — on stop: local transcription (parakeet, Apple MLX), then a
   headless Claude run writes:
   - Meeting note: TL;DR, decisions, action items, open questions
   - Rolling `TODO.md` (deduped, source-linked)
   - `People/<name>.md` mini-CRM entries
   - `INDEX.md` — one line per call ("which call was about what")
   - Persistent memory: commitments, feedback, project facts — so the
     assistant gets smarter about the user's work with every call.

## Surfaces to design

### 1. Menu bar item
- States: idle (icon only) · recording (icon + elapsed "12:04") ·
  processing (icon + "…").
- Constraint: template image = pure monochrome + alpha, ~18-22pt.
- Menu: Start/Stop, status line, Open Meeting Notes, Call Detection toggle,
  Show/Hide Live Transcript, Quit.

### 2. Call-detected popup (the hero moment)
- Now: 330×100 borderless NSPanel, dark (white 0.11 @ 0.97), radius 14,
  SF bold 14 title + SF 12 secondary, two standard NSButtons.
- Ask #2: make this feel like a product — spacing, type scale, button
  hierarchy (primary "Take notes"), maybe an icon slot, entrance animation.
  Reference: Granola's "Meeting detected / Take notes" card.

### 3. Live transcript panel
- Now: 340×400 same dark styling, "🪶 Quill — live" header, ✕ button,
  scrolling SF 12.5 text, "Me:"/"Them:" prefixes.
- Ask #3: speaker styling (color/weight per speaker instead of prefixes),
  readable line rhythm, subtle "● live" indicator, empty/loading states
  ("… loading model" → "● live").

### 4. The paper trail (markdown, Obsidian-rendered)
- Meeting note frontmatter + sections; INDEX.md list; TODO.md checkboxes;
  People pages. Ask #4: a consistent note aesthetic — heading order, emoji
  discipline, maybe a Quill footer mark on generated notes.

### 5. Moments that need copy/design love
- Permission onboarding (mic, system audio, Chrome automation) — currently
  raw macOS prompts plus README instructions. Ask #5: a friendly first-run
  checklist (even a static markdown/HTML page would help).
- Error notification ("Quill — error …") and the processing notification.

## Technical constraints for design

- All UI is AppKit (NSPanel/NSButton/NSTextView) driven from Python — no
  SwiftUI, no web views. Achievable: colors, corner radius, fonts, spacing,
  template images, simple layer effects. Hard: complex animation, blur
  materials (possible but extra work).
- Menu bar icon must read at 18px, monochrome.
- Popup and panel float over full-screen apps (Teams calls) — they must stay
  compact and unobtrusive.
- Everything ships as files in this repo: `assets/` for images, styling
  constants in `quill/panels.py`.

## Current file map

```
Quill/
├── quill/            python: cli, menubar, record, transcribe, live,
│                     process, micwatch, panels, config
├── capture/          audiocap.swift + Info.plist → bin/Audiocap.app
├── prompts/meeting.md   Claude's per-meeting instructions
├── assets/           menubar.png (template icon), quill.svg (logo seed)
├── launchd/com.tanmay.quill-menubar.plist
└── DESIGN.md         this brief
```

Data: recordings in `~/Meetings/`, notes in `~/Desktop/AI Brain/Meetings/`,
memory in the Claude project store.

## Deliverables wishlist (priority order)

1. Logo mark + wordmark (SVG, works at 16px and 512px, mono + color)
2. Menu bar icon set (idle/recording variants, template-ready)
3. Popup card redesign (spec: colors, type, spacing, button styles)
4. Live panel redesign (speaker treatment, live indicator, states)
5. Color story (ink/paper palette; one accent; dark-first)
6. First-run onboarding page
