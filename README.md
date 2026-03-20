# GitHub Cloud App — group-wide integration clone

This repository contains utilities to clone an existing **GitHub Cloud App** org integration from a **source Snyk Organization** to **other Snyk Organizations**, using the Snyk **v1 Integrations** API (`POST …/integrations/{integrationId}/clone`). Destinations are either **all orgs in a Snyk Group** (via the Groups API) or **org IDs listed in a file**.

## Prerequisites

- **Snyk Enterprise** access and an API token with permission to call the v1 API ([authentication](https://docs.snyk.io/snyk-api/v1-api)).
- **Groups** (and related org administration) enabled where Snyk requires it for integration cloning—see [Clone an integration across your Snyk Organizations](https://docs.snyk.io/snyk-platform-administration/snyk-broker/classic-broker/clone-an-integration-across-your-snyk-organizations) for product context.
- Shell tools: **`curl`**, **`jq`** (Bash script only).
- **Python 3.9+** for the Python script (stdlib only — no `pip` install).

## Scripts

| File | Purpose |
|------|---------|
| [`clone-github-cloud-app-to-group-orgs.sh`](./clone-github-cloud-app-to-group-orgs.sh) | Resolves the GitHub Cloud App integration in the source org, then clones it to each destination org — either every org in a group (API) or org IDs listed in a file. |
| [`clone_github_cloud_app_to_group_orgs.py`](./clone_github_cloud_app_to_group_orgs.py) | Same behavior as the shell script; accepts `--target-org-ids-file` / `-f` and other options on the command line. |

Make them executable once:

```bash
chmod +x clone-github-cloud-app-to-group-orgs.sh clone_github_cloud_app_to_group_orgs.py
```

## Environment variables

### Required

| Variable | Description |
|----------|-------------|
| `SNYK_API_KEY` | Snyk API token. Sent as `Authorization: token …` to the v1 API. |
| `SNYK_SOURCE_ORG_ID` | Public ID of the organization that **already** has the GitHub Cloud App integration configured (the clone **source**). |
| `SNYK_GROUP_ID` | Public ID of the Snyk Group used to **discover** destination orgs via the API. **Not required** if `SNYK_TARGET_ORG_IDS_FILE` is set. |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `SNYK_TARGET_ORG_IDS_FILE` | *(unset)* | Path to a text file: one destination org public ID per line. Blank lines and `#` comments are ignored; leading/trailing whitespace is trimmed. When set, the script does **not** call `GET /group/{groupId}/orgs` — only orgs from the file are targets. |
| `SNYK_API_BASE` | `https://api.snyk.io/v1` | Override for other regions, e.g. `https://api.eu.snyk.io/v1`. |
| `SNYK_INTEGRATION_TYPE` | `github-cloud-app` | Path segment used with `GET /org/{orgId}/integrations/{type}` to resolve the integration id when `SNYK_INTEGRATION_ID` is unset. |
| `SNYK_INTEGRATION_ID` | *(unset)* | If set, skips the lookup above; must be the integration’s public id in the source org. |
| `SNYK_DRY_RUN` | `0` | Set to `1` to **not** call the clone endpoint; prints what would be posted for each destination org. The integration `GET` still runs; the group org list `GET` runs only when `SNYK_TARGET_ORG_IDS_FILE` is unset. |
| `SNYK_PER_PAGE` | `100` | Page size for listing group orgs (v1 maximum is 100). |

Treat `SNYK_API_KEY` as a secret: avoid committing it, and prefer a password manager or `read -s` over leaving it in shell history.

## Usage

1. Export the required variables (and any optional ones you need).

2. **Recommended:** run a dry run first to confirm the destination org list and that the source integration resolves:

   ```bash
   export SNYK_API_KEY="…"
   export SNYK_GROUP_ID="…"
   export SNYK_SOURCE_ORG_ID="…"

   SNYK_DRY_RUN=1 ./clone-github-cloud-app-to-group-orgs.sh
   ```

3. Run with `SNYK_DRY_RUN=0` to perform the clones:

   ```bash
   ./clone-github-cloud-app-to-group-orgs.sh
   ```

One-liner style:

```bash
SNYK_API_KEY="…" SNYK_GROUP_ID="…" SNYK_SOURCE_ORG_ID="…" ./clone-github-cloud-app-to-group-orgs.sh
```

The script **skips** the source org (it only clones **to** other orgs).

**Destination list from a file** (no group org listing API call):

```bash
export SNYK_API_KEY="…"
export SNYK_SOURCE_ORG_ID="…"
export SNYK_TARGET_ORG_IDS_FILE="./target-orgs.txt"

SNYK_DRY_RUN=1 ./clone-github-cloud-app-to-group-orgs.sh
```

Example `target-orgs.txt`:

```text
# Production orgs
aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb
```

`SNYK_GROUP_ID` is omitted in that mode; you are responsible for ensuring each ID is a valid destination org your token can edit.

### Python (`clone_github_cloud_app_to_group_orgs.py`)

Configuration can come from the environment (same variables as the shell script) and/or flags. **`--target-org-ids-file` / `-f`** sets the org list file path (equivalent to `SNYK_TARGET_ORG_IDS_FILE`); if omitted, the env var is used when set.

```bash
export SNYK_API_KEY="…"
export SNYK_SOURCE_ORG_ID="…"

./clone_github_cloud_app_to_group_orgs.py --dry-run \
  --group-id "…"

./clone_github_cloud_app_to_group_orgs.py --no-dry-run \
  -f ./target-orgs.txt
```

Use `./clone_github_cloud_app_to_group_orgs.py --help` for all options (`--api-base`, `--integration-type`, `--integration-id`, `--per-page`, `--source-org-id`, `--group-id`, `--api-key`, etc.).

## Exit status

- **0** — All clone requests succeeded (or dry-run completed without clone calls).
- **Non-zero** — Initialization error, missing tools, or at least one clone request failed. Check stderr and the per-org error lines.

## API references

- [Integrations (v1)](https://docs.snyk.io/snyk-api/reference/integrations-v1) — clone and integration-by-type endpoints.
- [Groups (v1)](https://docs.snyk.io/snyk-api/reference/groups-v1) — list organizations in a group.

## Finding IDs

- **Group and organization public IDs** appear in the Snyk UI (org/group settings) and in API responses.
- Your token must be allowed to **list orgs** in the group and to **view/edit integrations** on the source and destination organizations, per the v1 reference for each endpoint.
