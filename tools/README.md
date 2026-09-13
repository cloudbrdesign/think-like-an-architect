# tools/

| Tool | Purpose |
|---|---|
| `boundary_check.py` | Education-mode boundary check: nothing commercial, nothing internal, no dependency on private repositories. Configured by `.tla/boundary.json`. |
| `tests/test_boundary_check.py` | Planted-violation fixture tests: each rule must be seen to fail. |

Run locally before pushing:

```
python3 tools/boundary_check.py --config .tla/boundary.json
python3 -m unittest discover -s tools/tests -v
```

Both use the Python standard library only and need no credentials or network access.
