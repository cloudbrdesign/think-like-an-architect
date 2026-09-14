# tools/

| Tool | Purpose |
|---|---|
| `boundary_check.py` | Education-mode boundary check: nothing commercial, nothing internal, no dependency on private repositories. Configured by `.tla/boundary.json`. |
| `commit_metadata_check.py` | Public commit metadata check: commits use the publisher identity (a platform committer is accepted on merge commits), and commit messages and pull request text carry no co-author, generated-with/by, assisted-by or session trailers or similar attribution lines. Configured by `.tla/commit_metadata.json`; runs in the `commit-metadata` workflow. |
| `tests/test_boundary_check.py` | Planted-violation fixture tests: each rule must be seen to fail. |
| `tests/test_commit_metadata_check.py` | Commit metadata tests: clean history and platform merge commits pass; commits planted in temporary repositories must be seen to fail. |

Run locally before pushing:

```
python3 tools/boundary_check.py --config .tla/boundary.json
python3 tools/commit_metadata_check.py --config .tla/commit_metadata.json --range origin/main..HEAD
python3 -m unittest discover -s tools/tests -v
```

All use the Python standard library only and need no credentials or network access.
