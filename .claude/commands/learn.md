# /learn — Capture a reusable insight

Phase 8 ("Learn") of the implementation playbook. Run after a slice lands, or any
time the session surfaced a non-obvious pattern, gotcha, or decision worth keeping.

Self-contained: writes to the project memory store — no external service required.

## When to invoke

- A slice just landed (playbook Phase 8/9).
- You hit a gotcha that cost real time and would bite again (e.g. an Odoo ORM
  quirk, a migration trap, a test-isolation issue).
- A decision was made that isn't obvious from the code or git history.
- The user says "remember this", "capture that", "/learn".

If nothing non-obvious happened, record an explicit "no new patterns this slice"
note in the slice's tracker row and stop — do not invent an insight.

## Procedure

1. **Name the insight** in one line — the reusable lesson, not the incident.
   Bad: "fixed the failing test". Good: "post_install tests need `-at_install`
   or they run against the un-upgraded module".

2. **Classify** it: `feedback` (how we should work), `project` (ongoing
   goal/constraint), `reference` (external pointer), or `user` (about the user).

3. **Write one memory file** under the project memory dir
   (`~/.claude/projects/<slug>/memory/<kebab-slug>.md`) with frontmatter:
   ```markdown
   ---
   name: <kebab-slug>
   description: <one-line summary used for recall>
   metadata:
     type: feedback | project | reference | user
   ---

   <the insight. For feedback/project, add **Why:** and **How to apply:** lines.>
   ```
   For a debugging gotcha, prefer a `reference` memory or a note in the module's
   own docs — do not duplicate what the code or CLAUDE.md already records.

4. **Index it**: append one line to that dir's `MEMORY.md`
   (`- [Title](file.md) — hook`). One line per memory; never put content there.

5. **Check for duplicates first** — update an existing file rather than adding a
   near-duplicate; delete memories later proven wrong.

## Output

Report: the slug written, its type, and the one-line hook. If you recorded
"no new patterns", say so plainly.
