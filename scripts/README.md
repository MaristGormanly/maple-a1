# scripts/

Operational helper scripts. Not imported by application code.

## demo_rag.py

Standalone demo of the RAG retrieval pipeline (ingest + retrieve). Used to
drive the screen-recorded walkthrough at `docs/demos/rag-demo.md`.

Prerequisites:
- Server virtualenv active with `server/requirements.txt` installed
- `OPENAI_API_KEY` and `DATABASE_URL` set
- `alembic upgrade head` already applied (creates `style_guide_chunks`)

Run from the repo root:

```bash
python scripts/demo_rag.py --ingest        # fetch + embed + insert all 5 style guides
python scripts/demo_rag.py --showcase      # canned queries across python/typescript/c++
python scripts/demo_rag.py --query "naming conventions" --lang python
```
