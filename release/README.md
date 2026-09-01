# GitHub-native release orchestrator R0

This replaces repeated copy/paste and manual scheduling with a reviewable GitHub control plane.

## Release path

1. Prepare an article on its own release branch and open a PR into `main`.
2. Review the PR and channel bundle.
3. Add or update the release entry in `release/release-queue.json`.
4. Set an explicit timezone-bearing `release_at` value, set `state` to `scheduled`, and set `approved` to `true`.
5. Mark the release PR ready for review and apply the `release-approved` label. The label is the final human publication authorization.
6. The hourly GitHub Action checks the queue. Once the time is due, it verifies the PR and label, merges the already-reviewed PR, and asks the existing distribution workflow to build the channel bundle.
7. The existing `publish.yml` push trigger publishes the updated Quarto site to GitHub Pages.

No queue date by itself can publish. No label by itself can publish. Both the machine-readable approval state and the human-applied PR label are required.

## Channel behavior

- **GitHub Pages:** canonical publication; triggered by the merge to `main`.
- **X:** direct API hook exists. It remains off unless the release entry has `channels.x_direct=true`, the repository variable `X_DIRECT_PUBLISH` is exactly `true`, and the `X_USER_ACCESS_TOKEN` secret is configured with user-context posting permission.
- **LinkedIn:** the existing distribution build produces the LinkedIn caption/PDF artifact. Direct API publication should only be enabled after LinkedIn grants the required member/application permissions.
- **Substack:** the existing distribution build produces the Substack edition. It remains an artifact/manual-last-mile channel until a stable supported publication interface is available.
- **Typefully:** retained only as an optional legacy path; it is not required by this orchestrator.

## Queue states

- `planned` — tracked, not eligible for release. `release_at` may be null.
- `scheduled` — must have `approved=true` and a timezone-bearing `release_at`.
- `released` — bookkeeping state after release if the queue is manually reconciled.
- `cancelled` — never eligible.

The executor is idempotent with respect to already-merged PRs: later hourly runs detect the merged PR and do not merge again.

## Dry-run

Use the workflow's `execute=false` option, or locally:

```bash
python scripts/release_orchestrator.py release/release-queue.json
```

A deterministic clock can be supplied for tests:

```bash
python scripts/release_orchestrator.py release/release-queue.json --now 2026-09-05T09:00:00+08:00
```

## Direct X setup

The X hook uses the official v2 `POST https://api.x.com/2/tweets` endpoint with a user-context OAuth access token. Store the user token only as the GitHub Actions secret `X_USER_ACCESS_TOKEN`; never commit it. Keep repository variable `X_DIRECT_PUBLISH` unset or `false` until a dry-run announcement is reviewed.

## Safety boundaries

- No customer data belongs in this public repository.
- Secrets remain GitHub Actions secrets, never queue fields or source files.
- Scheduled automation may merge only the PR number named in the approved queue entry.
- The named PR must target `main`, be open, non-draft, non-conflicting, and carry `release-approved`.
- LinkedIn/Substack remain generated artifacts unless separately authorized and integrated.
