# Reference index

`operator_index.json` and `reader_index.json` are generated from the live
classes and schemas. Read the JSON index first, then only the pages for the
operators you are considering. The workflow is in `../route_sop.md`; the
LLM and human entry points are `../llm_guide.md` and `../user_guide.md`.

Pages marked **Auto-generated** are derived from the declaration. If a
numerical/format edge case matters, read the linked source and tests, or add
a curated note under `notes/operators/` or `notes/readers/` and regenerate.

```bash
python scripts/build_reference_docs.py          # write pages/indexes
python scripts/build_reference_docs.py --check  # CI: pages must exist
```
