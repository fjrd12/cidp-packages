# ADR-0001: Package distribution mechanism for cidp-packages

**Status:** Accepted
**Date:** 2026-09-23
**Deciders:** Francisco Rodriguez

## Context

`cidp-packages` (the shared `bitso` adapter, `models`, and `common` retry
decorator) must be versioned and installable by other CIDP repos
(`cidp-ingestion`, `cidp-api`, later `cidp-features`/`cidp-rules`/etc.), each
pinning an exact version — never a floating reference (see the versioned-config
invariant this project applies broadly).

Constraints: polyrepo, all repos are private, under one personal GitHub
account (no org), no existing package registry infrastructure. V0 scope
should not stand up infra that isn't needed yet.

## Decision

Distribute `cidp-packages` via **pip installing directly from a Git tag**:

```
cidp-packages @ git+https://github.com/fjrd12/cidp-packages@v0.1.0
```

pinned in each consumer's `pyproject.toml`/`requirements.txt`. No package
registry (GitHub Packages, private PyPI) is stood up for V0.

## Options Considered

### Option A: git+tag pip install
| Dimension | Assessment |
|---|---|
| Complexity | Low — no extra service, no auth config beyond existing repo access |
| Cost | None |
| Scalability | Fine up to a handful of consumer repos; revisit if the org grows |
| Team familiarity | High — standard pip feature |

**Pros:** Zero new infra. Works immediately with the `gh`/git credentials
already in place for these private repos. Version pin is explicit and
auditable in consumer `pyproject.toml`.
**Cons:** Consumers need git-clone access to `cidp-packages` at install time
(fine today — same account owns everything); slightly slower installs than a
binary index; no wheel caching.

### Option B: GitHub Packages (private PyPI-compatible index)
| Dimension | Assessment |
|---|---|
| Complexity | Medium — requires per-repo `pip.conf`/`~/.netrc` auth, a publish step in CI, token scoping |
| Cost | None (included with GitHub) but adds moving parts |
| Scalability | Better long-term (proper index, wheel caching) |
| Team familiarity | Medium |

**Pros:** Proper package index; better story once there are many consumers or
external contributors.
**Cons:** Extra CI wiring and auth plumbing for a V0 with a single consumer
pair right now — infra ahead of need.

### Option C: Self-hosted/other private PyPI
Rejected outright for V0 — meaningfully more infra than either A or B for no
benefit at this scale.

## Trade-off Analysis

Option B is the more "proper" long-term answer, but it's infrastructure this
project doesn't need yet — V0 has exactly two consumers. Option A is fully
reversible: switching to Option B later only changes the dependency URL/index
in consumer manifests, not `cidp-packages`'s own layout.

## Consequences

- Easier: publishing is just `git tag v0.1.0 && git push --tags` — no
  publish pipeline to build/maintain yet.
- Harder: no wheel index browsing, no automatic dependency resolution
  across multiple `cidp-packages` versions in flight simultaneously (not a
  V0 concern with a single active version).
- Revisit: move to GitHub Packages (Option B) once there are 3+ consumer
  repos or contributors outside this account, per the "revisit" note above.

## Action Items
1. [x] `cidp-packages` ships as a normal installable Python package (`pyproject.toml`, `src/` layout).
2. [ ] Tag `v0.1.0` once CI is green.
3. [ ] Consumers pin `cidp-packages @ git+https://github.com/fjrd12/cidp-packages@v0.1.0` in their manifests.
