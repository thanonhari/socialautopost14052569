# SocialAutoPost Knowledge Wiki Instructions

This directory is a persistent LLM-maintained wiki for the `socialautopost` project.

## Purpose

Maintain durable project knowledge outside chat history:

- platform ingest behavior
- download experiments and outcomes
- tool setup notes
- known errors and fixes
- workflow decisions
- future implementation ideas

## Directory Layout

- `raw/sources/` immutable source notes, pasted references, saved articles
- `raw/transcripts/` source transcripts and extracted captions
- `raw/links.md` links worth revisiting
- `wiki/index.md` catalog of wiki pages
- `wiki/log.md` chronological activity log
- `wiki/platforms/` platform-specific ingest notes
- `wiki/tools/` tool setup and behavior
- `wiki/errors/` recurring errors and fixes
- `wiki/workflows/` project workflows
- `wiki/experiments/` test results and observations

## Maintenance Rules

When ingesting a new source or result:

1. Read relevant existing wiki pages first, starting with `wiki/index.md`.
2. Add or update a concise source/result page if the information is durable.
3. Update affected platform/tool/error/workflow pages.
4. Add cross-links using relative markdown links.
5. Update `wiki/index.md`.
6. Append one entry to `wiki/log.md`.

## Page Style

- Keep pages practical and project-specific.
- Prefer facts from observed commands over speculation.
- Use short sections: Summary, Current Behavior, Known Issues, Next Steps.
- Include command examples only when they are known to work locally.
- Preserve uncertainty explicitly with "Unknown" or "Needs verification".

## Source Policy

- `raw/` is source-of-truth input. Do not rewrite raw source files except to append new source notes.
- `wiki/` is synthesized project knowledge. It can be updated as understanding changes.
- If newer evidence contradicts older wiki content, update the affected page and mention the contradiction in `wiki/log.md`.

## Safety

Do not add instructions for bypassing copyright or access controls. For media ingest, document that workflows should be used only with content the user owns, has permission to use, or is otherwise lawful to process.
