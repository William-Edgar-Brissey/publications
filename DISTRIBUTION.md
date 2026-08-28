# Publication distribution system

This repository is the controlling source for every public edition. A release begins as one reviewed Quarto document and becomes several channel-native artifacts; it is not copied blindly into incompatible editors.

## Adopted stack

| Layer | Adopted technology | Role |
|---|---|---|
| Controlling source | GitHub + Quarto | Revision history, corrections, canonical HTML, and complete PDF |
| Web edition | Quarto + GitHub Pages | Canonical, searchable, accessible long-form publication |
| PDF edition | Quarto + KOMA-Script styling | Complete downloadable and LinkedIn document edition |
| X edition | Typefully API/MCP/Agent Skill | Native long-form X Article with cover, preview, comments, and approval |
| LinkedIn edition | Typefully document post | Complete PDF as a native LinkedIn document with a concise caption |
| Substack edition | Generated native Markdown + draft-only MCP pattern | Full newsletter draft, email preview, and deliberate final send |
| Authenticated UI execution | One bounded Grok Publisher Bot, when already included in an eligible plan | Creates or updates drafts in Substack and other unsupported channel UIs, then stops for approval |
| Social artwork | Repository-controlled 1600×900 covers | Consistent Open Graph, X, LinkedIn, and newsletter previews |

Typefully was selected over a generic scheduler because it explicitly supports X Articles, LinkedIn PDF documents, realistic previews, collaboration, an API, MCP, and an official Agent Skill. Postiz and Mixpost remain credible short-form schedulers, but self-hosting them would add infrastructure and platform-app maintenance without solving the long-form edition problem.

Substack is handled separately. Its documented public API does not expose general long-form publishing. The safe operating model is to create a private draft, review the web and email previews, and make the final send a deliberate human action. Session-cookie automation must not run in GitHub Actions or receive credentials through chat.

Grok Bot is an optional last-mile executor, not the source of content or design. Its early-beta cloud computer can work through authenticated interfaces that lack a reliable API, but it must consume the repository-generated bundle and follow `grok-bot-handoff.md`. Use one Publisher Bot with narrow channel ownership. Do not create overlapping bots, provide API secrets, permit source edits, or authorize an unattended publish. If Grok Bot is not already included in an eligible plan, the release bundle remains fully usable through ordinary private-draft workflows.

## Release workflow

1. Review and merge the controlling `.qmd` source.
2. Let `publish.yml` render canonical HTML and PDF editions.
3. Run **Build publication distribution bundle** from GitHub Actions.
4. Download and review the bundle against `channel-qa.md`.
5. When the Typefully connection is configured, rerun with **Create private X Article and LinkedIn document drafts** enabled.
6. Review the realistic X and LinkedIn previews in Typefully, then approve publication.
7. Create or update the private Substack draft from `substack-article.md` manually, with the draft-only MCP, or with one bounded Grok Publisher Bot following `grok-bot-handoff.md`.
8. Review the Substack web and email previews, then send deliberately.
9. Record every live URL in the release log before promotion begins.

## Required Typefully secrets

Add these in GitHub repository settings under **Secrets and variables → Actions**:

- `TYPEFULLY_API_KEY`
- `TYPEFULLY_SOCIAL_SET_ID`

The workflow creates private drafts only. It contains no automatic publish or schedule instruction.

## Generated bundle

For each article, `scripts/build_distribution.py` creates:

- `x-article.md` — complete X Article Markdown with unsupported tables converted to readable labeled records;
- `substack-article.md` — complete Substack-ready Markdown with the same semantic conversion;
- `linkedin-caption.txt` — concise caption for the attached complete PDF;
- the complete rendered PDF;
- the 1600×900 publication cover;
- `manifest.json` — controlling source, revision, canonical URL, and edition map; and
- `channel-qa.md` — mandatory visual and metadata review; and
- `grok-bot-handoff.md` — exact, bounded instructions for authenticated UI draft creation when that execution path is used.

## Publication rule

Automation may prepare, validate, upload, and create private drafts. It may not erase the distinction between a generated artifact and a reviewed public release. Final publication remains human-approved on every channel.
