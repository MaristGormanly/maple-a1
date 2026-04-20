# RAG Retrieval — Screen Recording Walkthrough

A 4–6 minute screen-recorded demo of the MAPLE A1 RAG pipeline: style guides
on the web → embeddings → pgvector → cosine similarity ranking → use inside
an evaluation.

## Prerequisites

Verify all of these *before* you start recording.

- `OPENAI_API_KEY` exported (real key — the demo uses live embeddings).
- `DATABASE_URL` exported and Postgres reachable with the `vector` extension.
- `alembic upgrade head` already applied (`style_guide_chunks` table exists).
- Server virtualenv active with `server/requirements.txt` installed.
- A dev JWT in hand. Generate with:
  ```bash
  python -c "from app.utils.security import create_access_token; print(create_access_token({'sub': 'dev', 'role': 'user'}))"
  ```
- A small public Python repo URL ready for the end-to-end scene.
- A pgvector-enabled Postgres reachable via `DATABASE_URL`. If running
  against a fresh local DB, build pgvector against your Postgres version
  (the Homebrew bottle currently only ships @17/@18 builds — older versions
  need to build from source) and `CREATE EXTENSION vector;` in the target
  database before `alembic upgrade heads` (note the plural — there are two
  migration heads).

Recording setup:
- macOS QuickTime Player → File → New Screen Recording.
- 1920×1080 window, terminal and editor font bumped for legibility.
- Two windows pre-arranged: editor on the left, terminal on the right.

## Scene 1 — Architecture (≈30s)

Open `server/app/services/rag_retriever.py`. Highlight lines 44–54.

Point at:
- `1 - (embedding <=> :qvec) AS cosine_sim` — the pgvector cosine operator.
- `WHERE language = :lang` — language-scoped retrieval.
- `LIMIT :k` and the `threshold` filter on line 68.

Narration cue: *"This is the entire retrieval surface — one SQL query, scoped
by language, ranked by cosine similarity, gated by a 0.75 threshold."*

## Scene 2 — Ingest (≈90s)

Switch to terminal. Run:

```bash
python scripts/demo_rag.py --ingest
```

Point at the stream of HTTP fetches (5 style guides) and the final
`Ingested N chunks in X.Xs.` line.

Then drop into psql to prove rows landed:

```bash
psql "$DATABASE_URL" -c "SELECT language, COUNT(*) FROM style_guide_chunks GROUP BY language;"
```

Narration cue: *"Five canonical style guides — PEP 8, Oracle Java, ts.dev,
Google JavaScript, Google C++ — fetched, chunked by heading, embedded with
text-embedding-3-large, and inserted into pgvector."*

## Scene 3 — Retrieval (≈90s)

Run:

```bash
python scripts/demo_rag.py --showcase
```

Point at:
- The three successful queries returning ranked chunks with cosine scores
  (C++ "include guards" tops out around 0.72; Python "naming conventions"
  and JS "let const var" land in the 0.50–0.56 range).
- The language filter switching across `c++`, `python`, `javascript`.
- The fourth query (`favorite pizza toppings`) returning zero hits — a
  deliberate `no_match` case so viewers see the threshold doing its job.

Optionally tail the server log in a side pane to show the
`retrieval_status: no_match` JSON line emitted by `rag_retriever.py:72`.

The showcase uses a `threshold=0.50` floor (not the production default of
0.75) because `text-embedding-3-large` at 1536 dims with these chunk sizes
clusters genuine matches in the 0.50–0.75 range; calibrating the production
threshold is tracked separately. Irrelevant queries still score under 0.10,
so the gate's purpose is unaffected.

Narration cue: *"Each query is embedded, compared against every chunk in the
language partition, and only results above the cosine threshold come back.
Below that, we log no_match instead of hallucinating context."*

## Scene 4 — End-to-end (≈90s)

Start the backend in a fresh pane:

```bash
uvicorn server.app.main:app --reload
```

In another pane, submit a small Python repo:

```bash
TOKEN="<paste dev JWT>"
curl -X POST http://localhost:8000/api/v1/code-eval/evaluate \
  -H "Authorization: Bearer $TOKEN" \
  -F "github_url=https://github.com/<small-public-python-repo>" \
  -F "rubric=@docs/demos/sample-rubric.json"
```

Capture the returned `submission_id`. Then poll:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/code-eval/submissions/<submission_id>
```

Point at:
- The uvicorn log line showing Pass 2 firing and the retriever being called.
- The submission response — specifically `style_guide_version` populated in
  the metadata, proving a retrieved chunk fed the LLM context.

Narration cue: *"In the real flow, retrieval is invoked from inside Pass 2.
The version of the style guide used is bubbled up into the submission
metadata, so reviewers can trace any feedback back to the exact source."*

## Scene 5 — Wrap (≈30s)

Back in the editor, briefly show:
- `server/app/services/pipeline.py:70` — the lazy import of
  `retrieve_style_chunks`.
- `server/app/services/ai_passes.py:412` — the call site inside Pass 2.

Narration cue: *"That's the whole loop — ingest once, retrieve per query,
plug into the evaluation pipeline."*

## Post-production

```bash
ffmpeg -i recording.mov -vcodec libx264 -crf 23 rag-demo.mp4
```

Drop the final `.mp4` into the team's shared drive and link it from the
milestone-2 status doc.
