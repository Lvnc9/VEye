# Prompt for opening a new chat (paste as-is, fill the last line)

```
You are continuing VEye V2 — a Persian RTL controlled-document system (Django + DRF + PostgreSQL + Redis + Celery + Next.js 16, all
storage local), being rewritten from a desktop app. The repo is /Users/samlv/WorkFlow/VEye/V_2.0 (GitHub: Lvnc9/VEye). The old app is
../V_1.0 (a separate repo with committed credentials — read it for behaviour, never copy secrets).

START HERE — do not re-read the whole project:
1. Read CLAUDE.md, then docs/README.md (status table, ground rules, docs index). Read only the doc for the area you touch.
2. Read docs/00-git-and-tracking.md. Commit every slice with those conventions (one slice per commit, verification in the body,
   CHANGELOG.md + docs updated in the same commit). Push only when I ask.
3. `git log --oneline | head -30` and CHANGELOG.md show what has already been done; docs/07-known-gaps.md lists open decisions.
4. docs/01-run-and-test.md for running and testing (Docker Desktop must be running; `docker compose restart celery` after task changes).

RULES: ask me before deciding product behaviour (batch questions, recommend an option for each); preserve the user's PDF algorithm's
quirks; Persian for all user-facing text; never type passwords into forms (ask me to sign in); report honestly what was and wasn't verified.

TASK: <describe the task here>
```
