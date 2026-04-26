# Project Study Pack Export

Regenerate the NotebookLM study pack from the repository root:

```bash
python docs/export/build_project_pdf.py
```

Outputs:

- `docs/export/AML_project_full_study_pack.md`
- `docs/export/AML_project_full_study_pack.pdf`

The export is intentionally focused on the simplified AML analytics project. Advanced files in `experimental/` are included as optional/non-core context, while heavy folders and binary artifacts are skipped.
