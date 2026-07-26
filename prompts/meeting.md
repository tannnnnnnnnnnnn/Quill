You are processing a recorded work meeting for {{USER}}. Do all five steps, then print exactly one final line `NOTE: <absolute path of the meeting note you wrote>`.

Meeting facts:
- Transcript: {{TRANSCRIPT_PATH}} (speakers: **Me** = {{USER}}, **Them** = other participants)
- Date/time: {{DATETIME}} — Duration: {{DURATION_MIN}} min — Title hint: "{{TITLE_HINT}}"

## Step 1 — read
Read the transcript fully. It is machine-transcribed: expect occasional wrong words; use context. Never invent facts not supported by the transcript.

**The Me track is the least trustworthy part of the transcript.** It comes from the raw microphone, which hears the whole room — music, a TV, someone else talking nearby, a video playing — and every bit of that is labelled **Me** as if {{USER}} said it. Measured on a real recording: ambient audio arrives at the same loudness as genuine speech, so nothing upstream can separate them.

Treat a **Me** line as real only when it fits the conversation: it answers a **Them** line, continues {{USER}}'s own point, or carries meeting content. Lines that read like song lyrics, an advert, a film, or free-associating nonsense are the room, not {{USER}} — leave them out of the note entirely rather than reasoning about them. Never build a decision, action item, or People note on a **Me** line that nothing else in the call supports. If a stretch of the Me track is clearly not {{USER}}, say so once in the Notes section and move on.

## Step 2 — meeting note
Write `{{NOTES_DIR}}/{{DATE}} <Short Title>.md` (concise title from content if hint is empty; keep the `{{DATE}} ` prefix):

```
---
date: {{DATETIME}}
attendees: [names inferable from transcript, else "unknown"]
tags: [meeting]
---

## TL;DR
2-4 sentences.

## Decisions
- ... (omit section if none)

## Action items
- [ ] task — owner 📅 YYYY-MM-DD
(only real commitments; date only if stated or clearly inferable; owner "Me" for {{USER}}'s items)

## Open questions
- ... (omit if none)

## Summary
The meeting as a story, chronological, one short paragraph per topic/phase —
what was discussed, who pushed for what, how it was resolved. Detailed enough
that a reader knows what happened without opening the transcript (this is the
Granola-style summarized transcript). Plain paragraphs, 150-400 words
depending on meeting length.

## Notes
Brief topic-by-topic bullets.

---
Transcript: [[Transcripts/{{TRANSCRIPT_NAME}}]]
```

## Step 2.5 — meeting index
Append one line to `{{NOTES_DIR}}/INDEX.md` (create with a `# Meetings` heading if missing):
`- {{DATE}} — [[<note filename without .md>]] — <one line: what this call was about>`

## Step 3 — rolling TODO
Read `{{TODO}}`. Add {{USER}}'s NEW action items from this meeting under the `## Inbox` heading as `- [ ] task 📅 YYYY-MM-DD (from [[<note filename without .md>]])`. Skip anything already present (match by meaning, not exact words). Never delete, edit, or reorder existing lines.

## Step 4 — people notes
For each participant with a real name in the transcript: update `{{PEOPLE_DIR}}/<Name>.md`. Create if missing with a one-line header (role/team if learnable). Append under `## Log`: `- {{DATE}}: <one line — what they discussed/committed/asked>`. Skip participants whose names never appear.

## Step 5 — memory distill
Persistent memory dir: `{{MEMORY_DIR}}`. Save only durable facts useful weeks from now — typically 0-4 per meeting; skip minutiae:
- commitments {{USER}} made, with deadlines → type: project
- feedback or guidance on HOW {{USER}} should work → type: feedback (include **Why:** and **How to apply:** lines)
- stable facts: people, projects, tools, decisions → type: project

Each memory = one file `<kebab-slug>.md`:
```
---
name: <kebab-slug>
description: <one-line summary>
metadata:
  type: project | feedback | user
---

<the fact, 1-4 sentences, absolute dates>
```
First check existing files in the dir (read MEMORY.md index + relevant files) — update an existing file rather than duplicating. Keep `{{MEMORY_DIR}}/MEMORY.md` index current: one line per memory, format `- [Title](file.md) — hook`.

Then print the final `NOTE: ` line.
