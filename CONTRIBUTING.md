# Contributing and repository rules

## How changes reach `main`

```
feature branch → validation → pull request → maintainer review → merge
```

- **`main` is human-controlled.** Direct writes to `main` are not the development mechanism.
- **The maintainer approves every merge.** A passing CI run is required, but it is not merge approval.
- Branches are short-lived and named for traceability, e.g. `episode-01/engagement`,
  `episode-01/architecture`, `episode-01/implementation`, `episode-01/validation`. No long-lived branches.
- Every pull request uses the template in `.github/pull_request_template.md`.

## Boundary rules — this is the free education repository

A learner must be able to complete every engagement from this repository alone. Therefore:

1. **No commercial source.** Production Deployment Pack material never enters this repository, on any branch.
2. **No dependency on private repositories:** no submodules, no downloads of private source, no private credentials in
   CI, no generation from private templates.
3. **No internal identifiers:** no local filesystem paths, usernames, account IDs, ARNs, keys or internal URLs.
4. The boundary is checked automatically in CI; a failing boundary check blocks review.

## Commit identity

Commits use the CloudBrewery publisher identity, and commit messages describe the change to the repository.
