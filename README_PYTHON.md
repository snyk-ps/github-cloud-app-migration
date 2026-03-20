# GitHub Cloud App clone — Python tool

This guide explains how to use **`clone_github_cloud_app_to_group_orgs.py`** to copy your existing **GitHub Cloud App** integration from one Snyk organization (the “source”) to other Snyk organizations.

You do **not** need to install extra Python packages. The script uses only the standard library and works on **Python 3.9 or newer**.

---

## What you need first

1. **A Snyk API token** with permission to use the Snyk API and to manage integrations on the organizations you care about. Create or copy it from your [Snyk account settings](https://snyk.io/account/).
2. **The source organization ID** — the Snyk org that *already* has GitHub Cloud App set up the way you want. That integration is what gets copied.
3. **Where to copy it — pick one:**
   - **Option A — whole group:** the **group ID** of a Snyk group, so every org in that group (except the source) is a target, or  
   - **Option B — a list file:** a text file listing only the **destination organization IDs** you want (one per line).

If you use Option A, your token must be able to list organizations in that group. If you use Option B, you must know the destination org IDs yourself (for example from the Snyk UI or your own records).

---

## Quick start (recommended)

Always do a **dry run** first. It talks to Snyk to resolve the integration and (if you use a group) to list orgs, but it does **not** perform any clones.

```bash
export SNYK_API_KEY="your-token"
export SNYK_SOURCE_ORG_ID="source-org-uuid"

# Option A — all orgs in a group (except the source)
python3 clone_github_cloud_app_to_group_orgs.py --dry-run --group-id "your-group-uuid"

# Option B — orgs listed in a file
python3 clone_github_cloud_app_to_group_orgs.py --dry-run \
  -f path/to/orgs.txt
```

Review the output. When you are ready to apply the clones, run the same command with **`--no-dry-run`** instead of `--dry-run` (or set `SNYK_DRY_RUN=0` and omit the dry-run flags — see below).

---

## Choosing targets: group vs file

| Approach | What to provide | When it fits |
|----------|-----------------|--------------|
| **Group** | `--group-id` or `SNYK_GROUP_ID` | You want every org under a Snyk group to receive the clone (the source org is skipped automatically). |
| **File** | `-f` / `--target-org-ids-file` or `SNYK_TARGET_ORG_IDS_FILE` | You only want specific destination orgs, or you do not use group listing. You do **not** need `--group-id` in this mode. |

If you pass **`--group-id`** while also using **`-f`**, the group ID is ignored and a short notice is printed.

---

## Target org file format

When you use **`-f`**, the file should be plain text:

- One **destination** organization ID per line (UUID format).
- Empty lines are ignored.
- Lines starting with **`#`** are treated as comments.
- Spaces at the start or end of a line are removed.

Example:

```text
# Staging and prod orgs
aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb
```

The script does **not** clone *to* the source org if it appears in this file; it skips that ID.

---

## Environment variables

You can keep secrets and IDs in the environment instead of passing them on the command line (often safer for the API token).

| Variable | Purpose |
|----------|---------|
| `SNYK_API_KEY` | **Required.** Your Snyk API token. |
| `SNYK_SOURCE_ORG_ID` | **Required.** Source org (where GitHub Cloud App is already configured). |
| `SNYK_GROUP_ID` | Required **unless** you use a target org file. Identifies the group whose orgs are listed via the API. |
| `SNYK_TARGET_ORG_IDS_FILE` | Optional path to the org list file. The **`-f` / `--target-org-ids-file`** argument overrides this if you pass it. |
| `SNYK_DRY_RUN` | If set to `1`, `true`, `yes`, or `on`, no clone requests are sent. Command-line **`--dry-run`** / **`--no-dry-run`** overrides this when you use them. |
| `SNYK_API_BASE` | Optional. Default is US v1 API: `https://api.snyk.io/v1`. For EU, use `https://api.eu.snyk.io/v1` (and the matching region for your tenant). |
| `SNYK_INTEGRATION_TYPE` | Optional. Default `github-cloud-app`. |
| `SNYK_INTEGRATION_ID` | Optional. If set, the script skips looking up the integration by type and uses this ID in the source org. |
| `SNYK_PER_PAGE` | Optional. Page size when listing orgs in a group (default `100`). |

---

## Command-line options

For the full list of flags and defaults, run:

```bash
python3 clone_github_cloud_app_to_group_orgs.py --help
```

Common flags:

| Flag | Meaning |
|------|---------|
| `-f`, `--target-org-ids-file` | Path to the file of destination org IDs. |
| `--source-org-id` | Source organization ID. |
| `--group-id` | Group ID (for API-based org listing). |
| `--api-key` | API token (prefer `SNYK_API_KEY` in the environment instead). |
| `--dry-run` | Plan only; no clones. |
| `--no-dry-run` | Perform clones; overrides `SNYK_DRY_RUN=1`. |

---

## Exit status

- **0** — Finished without clone failures (or dry run completed).
- **1** — Missing configuration, API error during setup, or at least one clone failed.

---

## Security tips

- Treat **`SNYK_API_KEY`** like a password: do not commit it, paste it into tickets, or pass it on shared screens if you can avoid it.
- Prefer **`export SNYK_API_KEY=...`** in a private shell session or your own secret store over putting the token in shell history with `--api-key`.

---

## More detail

- Snyk’s v1 API (integrations and groups): [Integrations (v1)](https://docs.snyk.io/snyk-api/reference/integrations-v1), [Groups (v1)](https://docs.snyk.io/snyk-api/reference/groups-v1).
- Shell script with the same behavior: see the main [README.md](./README.md).
