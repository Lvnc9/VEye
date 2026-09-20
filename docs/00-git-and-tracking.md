# Git, tracking and docs conventions

Why this exists: the project is too big to hold in one chat. **Git history + `CHANGELOG.md` + `docs/` are the memory.**
A new chat (or a new person) should be able to answer "what changed, why, and how was it checked?" from them alone.

## Repository layout
- The repo root is `V_2.0/` (remote `https://github.com/Lvnc9/VEye`, branch `main`).
  `backend/`, `frontend/`, `docs/`, `docker-compose.yml`, `.env.example`, `CHANGELOG.md`, `CLAUDE.md`.
- `V_1.0` (the old desktop app) is **not** in this repo. It is a sibling directory in the workspace (`../V_1.0`) with its own
  repo (`Lvnc9/VEye-GUI-customtkinter`) whose history contains committed credentials. **Never copy files from it into this repo**
  except through the documented importer/fixtures paths, and never its secrets.
- Local-only files are git-ignored: `.env`, `backend/media/`, `*.db`, `.claude/settings.local.json`.
  `.env.example` is the template and is tracked.

## History note
Phases 0–5 reached GitHub as a squashed snapshot (`504f945` … `a8de53a`), so **git history does not show them slice by slice** —
`CHANGELOG.md` and the per-area docs do. From Phase 6 on, every slice is its own commit.

## Commit format (Conventional Commits)
```
type(scope): imperative summary, ≤ 72 chars, no trailing period

Why this change exists (the problem, not a restatement of the diff).
What was decided, and by whom ("Decided with the user: …").
Behavioural differences from V_1.0, if any.

Verification: which tests/checks ran and their counts; what was checked in the
browser / live stack; mutation checks. Not verified: anything skipped, honestly.
Docs: which docs/CHANGELOG entries this commit updates.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```
- **types:** `feat` `fix` `refactor` `test` `docs` `chore` `perf` `build` `revert`
- **scopes:** `accounts` `core` `documents` `workflow` `verify` `pdfgen` `dashboard` `history` `bulk-print` `importer` `frontend` `docker` `git` `docs`
- `git commit` uses `.gitmessage` as a template (set with `git config --local commit.template .gitmessage`).

## One slice = one commit
- A **vertical slice** (model + migration + service + API + UI + tests + docs + changelog line) is one commit that leaves the tree green.
- Fixes, refactors and chores found on the way are **their own commits**, made *before* the feature that needed them.
- Docs-only changes are `docs:` commits. Test-only changes are `test:` commits.
- A migration is always committed with the model change that needs it. Never commit a generated migration you didn't read.
- Don't mix unrelated changes; don't commit half-working code "to save progress" on `main`.

## Before every commit (checklist)
1. `docker compose exec -T backend python manage.py test --noinput` — all green (state the count in the body).
2. `manage.py check` and `makemigrations --check --dry-run` clean.
3. Frontend touched → `npx tsc --noEmit`, `npm run lint`, `npx vitest run` (and `npm run build` for route changes).
4. `git status` / `git diff --staged` reviewed: **no `.env`, media, secrets, `__pycache__`, personnel data, or V_1.0 files.**
5. `CHANGELOG.md` `[Unreleased]` has a line for it, and the relevant doc + `docs/README.md` status table are updated **in the same commit**.

## Docs are part of the change
- Behaviour change → update the per-area doc (`docs/0x-*.md`), `docs/07-known-gaps.md` (open items / decisions), and, when a phase finishes,
  the `docs/README.md` status table and `docs/skeleton.md` §7.
- Decisions the user made go in the docs **and** the commit body, so they aren't re-asked.
- Say plainly what was *not* verified (known-gaps "Unverified by hand").

## Pushing and history safety
- **Push only when the user asks.** Never force-push. Never rewrite pushed history (`a8de53a` and everything before it is published).
- Work on `main` in small commits unless the user asks for a branch; if a branch is used: `phase-N/short-topic`.

## Finding things later
```bash
git log --oneline                        # the story, one line per slice
git log --grep "importer"                # everything about a topic
git log -p --follow -- path/to/file      # why a file is the way it is
git show <sha>                           # one slice with its verification notes
git log --format='%h %ad %s' --date=short -- docs/   # when the docs changed
```
Then `CHANGELOG.md` for the phase-level view and `docs/README.md` for the current state.
