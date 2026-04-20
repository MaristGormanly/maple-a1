# Milestone 1 Repository Pre-processor Prompts

## Purpose

This file contains ready-to-use prompts for Milestone 1, Task 2:

- Implement Repository Pre-processor: strip `node_modules`, `venv`, compiled binaries, `.git`

These prompts are designed to keep implementation aligned with:

- `milestone-01-tasks.md`
- `design-doc.md`
- `milestone-01-pat-cloning-process.md`

The goal is to build the preprocessing slice cleanly without drifting from the current Milestone 1 scope.

---

## Prompt 1: Read Requirements And Plan

Use this first to make the assistant gather context before editing code.

```text
Read these files carefully and summarize the exact requirements for Milestone 1, Task 2:

- milestone-01-tasks.md
- design-doc.md
- milestone-01-pat-cloning-process.md
- server/app/main.py

Focus only on the repository pre-processor requirement:
- strip node_modules
- strip venv
- strip compiled binaries
- strip .git

Then produce:
1. A short summary of the required behavior
2. A list of files you expect to create or edit
3. A concise implementation plan
4. Any ambiguities or risks

Important constraints:
- Stay within Milestone 1 scope
- Do not add AI grading, Docker execution, database persistence, or caching yet
- Do not change Task 1 clone behavior unless absolutely necessary for Task 2
- Keep the solution compatible with later caching and evaluation steps
```

---

## Prompt 2: Implement The Pre-processor

Use this after the planning prompt.

```text
Implement Milestone 1, Task 2: Repository Pre-processor.

Requirements:
- The pre-processor should operate on a cloned local repository path under data/raw/
- Remove directories named:
  - .git
  - node_modules
  - venv
- Also remove common virtualenv/cache variants when appropriate:
  - .venv
  - __pycache__
- Remove compiled/binary artifacts such as:
  - .pyc
  - .pyo
  - .so
  - .dll
  - .dylib
  - .exe
  - .class
  - .jar
  - .o
  - .obj
  - and other conservative compiled outputs if clearly appropriate

Implementation expectations:
- Create a dedicated preprocessing utility/module rather than burying all logic inside the route handler
- Keep the logic deterministic and safe
- Preserve source files and project structure outside the stripped artifacts
- Return or expose enough information for later debugging or extension if helpful
- Use clear names and keep the code easy to test

Milestone alignment:
- This pre-processor exists to reduce noise before later analysis
- It should be compatible with later caching, persistence, and evaluation work
- Avoid broad deletion rules that might remove legitimate student source files
- Keep the implementation ASCII unless the file already uses non-ASCII

After implementation:
- Run lint or diagnostics for changed files
- Run a lightweight verification that the pre-processor removes the targeted directories/files
- Summarize exactly what changed
```

---

## Prompt 3: Integrate Without Breaking Task 1

Use this if you want the assistant to connect the pre-processor into the flow carefully.

```text
Integrate the repository pre-processor into the current Milestone 1 backend flow, but do not break the Task 1 cloning contract.

Current requirement to preserve:
- The GitHub PAT cloning task should still accurately support clone + commit hash capture

Integration guidance:
- Decide whether preprocessing should happen:
  1. immediately after clone in a separate step, or
  2. in a distinct follow-up workflow callable after clone

Use the requirements docs to justify the choice before editing.

Important:
- If integration changes the API response semantics, explain why
- Do not silently drift from the documented behavior
- If the docs conflict, call out the conflict and choose the more Milestone-accurate behavior
- Keep error responses structured and consistent

After changes:
- Verify clone behavior still works
- Verify preprocessing works
- Verify the route response still matches the intended Milestone contract
```

---

## Prompt 4: Add Tests For The Pre-processor

Use this if you want the assistant to create repeatable tests instead of only ad hoc checks.

```text
Add automated tests for the Milestone 1 repository pre-processor.

Test scenarios should include:
1. A fixture repo containing .git, node_modules, venv, .venv, __pycache__, and compiled artifacts
2. Confirmation that those paths/files are removed
3. Confirmation that normal source files remain
4. A nested directory case
5. A missing or invalid repository path case

Constraints:
- Keep tests lightweight and local
- Do not require Docker
- Do not require a live GitHub call for these tests
- Prefer deterministic fixtures over external dependencies

If the repository does not yet have a test structure, create the smallest reasonable one for this task.
Then run the tests and report the results.
```

---

## Prompt 5: Review For Spec Alignment

Use this after implementation and testing.

```text
Review the repository pre-processor implementation against these requirements sources:

- milestone-01-tasks.md
- milestone-01-pat-cloning-process.md
- design-doc.md

Focus on:
- whether it strips node_modules, venv, compiled binaries, and .git
- whether it stays within Milestone 1 scope
- whether it preserves files that should not be removed
- whether it is compatible with later caching and evaluation work
- whether testing coverage is sufficient for this task

Return:
1. Findings first, ordered by severity
2. Any requirement mismatches
3. Residual risks
4. A brief final verdict on whether Task 2 is complete
```

---

## One-Shot Prompt

Use this if you want a single prompt instead of the staged workflow above.

```text
Implement Milestone 1, Task 2: Repository Pre-processor: strip node_modules, venv, compiled binaries, and .git.

Before editing, read:
- milestone-01-tasks.md
- milestone-01-pat-cloning-process.md
- design-doc.md
- server/app/main.py

Then:
1. Summarize the exact Task 2 requirements
2. Implement the preprocessing logic in a dedicated backend utility/module
3. Integrate it in the most Milestone-accurate way without drifting from the Task 1 clone contract unless the docs clearly require it
4. Add or run lightweight tests that verify targeted paths are removed and normal source files remain
5. Check lint/diagnostics for changed files
6. Report any remaining requirement gaps

Constraints:
- Stay within Milestone 1 scope only
- Do not add AI grading, Docker execution, database work, or caching in this task
- Keep deletion rules conservative
- Preserve a clean, structured response contract if route behavior is affected
- Call out any conflict between docs instead of guessing
```
