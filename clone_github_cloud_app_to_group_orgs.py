#!/usr/bin/env python3
"""
Clone a GitHub Cloud App org integration from a source Snyk Organization to other
organizations (all orgs in a group via API, or org IDs listed in a file).

Uses the Snyk v1 API:
  https://docs.snyk.io/snyk-api/reference/integrations-v1
  https://docs.snyk.io/snyk-api/reference/groups-v1

Environment (typical):
  SNYK_API_KEY          Required unless passed as --api-key
  SNYK_SOURCE_ORG_ID    Required unless passed as --source-org-id
  SNYK_GROUP_ID         Required when not using a target org file
  SNYK_DRY_RUN          If 1, do not POST clone (overridden by --dry-run / --no-dry-run)

Optional env:
  SNYK_API_BASE, SNYK_INTEGRATION_TYPE, SNYK_INTEGRATION_ID, SNYK_PER_PAGE
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


def _bool_env(name: str, default: bool = False) -> bool:
    v = _env(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _trim(s: str) -> str:
    return s.strip()


def _request(
    method: str,
    base_url: str,
    path: str,
    api_key: str,
    *,
    body: dict[str, Any] | None = None,
) -> tuple[int, bytes]:
    url = base_url.rstrip("/") + path
    data: bytes | None = None
    headers = {
        "Authorization": f"token {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"HTTP request failed: {e.reason}") from e


def _get_json(
    base_url: str, path: str, api_key: str
) -> tuple[bool, dict[str, Any] | list[Any] | None, str]:
    code, raw = _request("GET", base_url, path, api_key)
    text = raw.decode("utf-8", errors="replace")
    if code < 200 or code >= 300:
        return False, None, text
    try:
        return True, json.loads(text), text
    except json.JSONDecodeError:
        return False, None, text


def _post_json(
    base_url: str, path: str, api_key: str, body: dict[str, Any]
) -> tuple[bool, dict[str, Any] | None, str]:
    code, raw = _request("POST", base_url, path, api_key, body=body)
    text = raw.decode("utf-8", errors="replace")
    if code < 200 or code >= 300:
        return False, None, text
    try:
        return True, json.loads(text), text
    except json.JSONDecodeError:
        return True, None, text


def collect_org_ids_from_group(
    base_url: str, api_key: str, group_id: str, per_page: int
) -> list[str]:
    out: list[str] = []
    offset = 0
    while True:
        path = f"/group/{group_id}/orgs?perPage={per_page}&page={offset}"
        ok, data, err = _get_json(base_url, path, api_key)
        if not ok or not isinstance(data, dict):
            raise RuntimeError(
                f"Failed to list orgs for group {group_id}: {err[:500]}"
            )
        orgs = data.get("orgs") or []
        if not orgs:
            break
        for o in orgs:
            oid = o.get("id")
            if oid:
                out.append(str(oid))
        if len(orgs) < per_page:
            break
        offset += per_page
    return out


def collect_org_ids_from_file(path: str) -> list[str]:
    p = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(p):
        raise FileNotFoundError(f"Not a regular file: {p}")
    ids: list[str] = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = _trim(line)
            if not line or line.startswith("#"):
                continue
            ids.append(line)
    return sorted(set(ids))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clone GitHub Cloud App integration from a source org to other orgs "
        "(group API or org list file)."
    )
    parser.add_argument(
        "--target-org-ids-file",
        "-f",
        metavar="PATH",
        default=_env("SNYK_TARGET_ORG_IDS_FILE"),
        help="File of destination org public IDs (one per line). Same rules as the shell "
        "script: blank lines and # comments ignored; whitespace trimmed. "
        "If set, GET /group/.../orgs is not used. (Env: SNYK_TARGET_ORG_IDS_FILE)",
    )
    parser.add_argument(
        "--source-org-id",
        default=_env("SNYK_SOURCE_ORG_ID"),
        help="Source org public ID (env: SNYK_SOURCE_ORG_ID)",
    )
    parser.add_argument(
        "--group-id",
        default=_env("SNYK_GROUP_ID"),
        help="Group ID for listing orgs (env: SNYK_GROUP_ID). Not required with -f.",
    )
    parser.add_argument(
        "--api-key",
        default=_env("SNYK_API_KEY"),
        help="Snyk API token (env: SNYK_API_KEY). Prefer the environment variable.",
    )
    parser.add_argument(
        "--api-base",
        default=_env("SNYK_API_BASE", "https://api.snyk.io/v1"),
        help="v1 API base URL (default: https://api.snyk.io/v1)",
    )
    parser.add_argument(
        "--integration-type",
        default=_env("SNYK_INTEGRATION_TYPE", "github-cloud-app"),
        help="Integration type for GET by type (default: github-cloud-app)",
    )
    parser.add_argument(
        "--integration-id",
        default=_env("SNYK_INTEGRATION_ID"),
        help="Skip lookup; use this integration id in the source org (env: SNYK_INTEGRATION_ID)",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=int(_env("SNYK_PER_PAGE", "100") or "100"),
        help="Page size for group org listing (default: 100)",
    )
    dry = parser.add_mutually_exclusive_group()
    dry.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Do not POST clone requests",
    )
    dry.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Perform clone POST requests (overrides SNYK_DRY_RUN=1)",
    )
    args = parser.parse_args()

    target_file = (args.target_org_ids_file or "").strip() or None

    api_key = args.api_key
    if not api_key:
        print("SNYK_API_KEY or --api-key is required.", file=sys.stderr)
        return 1
    source_org = args.source_org_id
    if not source_org:
        print("SNYK_SOURCE_ORG_ID or --source-org-id is required.", file=sys.stderr)
        return 1

    if not target_file:
        if not args.group_id:
            print(
                "SNYK_GROUP_ID or --group-id is required when --target-org-ids-file is not set.",
                file=sys.stderr,
            )
            return 1
    elif args.group_id:
        print(
            "Note: --group-id is ignored when --target-org-ids-file is set.",
            file=sys.stderr,
        )

    if args.dry_run is True:
        dry_run = True
    elif args.no_dry_run is True:
        dry_run = False
    else:
        dry_run = _bool_env("SNYK_DRY_RUN", False)

    base_url = args.api_base
    int_type = args.integration_type
    per_page = args.per_page

    integration_id = (args.integration_id or "").strip()
    if not integration_id:
        print(
            f"Resolving integration id for type {int_type!r} in source org {source_org}..."
        )
        ok, data, err = _get_json(
            base_url, f"/org/{source_org}/integrations/{int_type}", api_key
        )
        if not ok or not isinstance(data, dict):
            print(
                f"Failed to GET integration by type: {err[:2000]}",
                file=sys.stderr,
            )
            return 1
        integration_id = str(data.get("id") or "")
        if not integration_id:
            print("Could not read .id from integration response.", file=sys.stderr)
            return 1
        print(f"Using integration id: {integration_id}")
    else:
        print(f"Using integration id from env/CLI: {integration_id}")

    if target_file:
        print(f"Loading destination org IDs from {target_file!r}")
        try:
            all_org_ids = collect_org_ids_from_file(target_file)
        except OSError as e:
            print(e, file=sys.stderr)
            return 1
        if not all_org_ids:
            print(
                "No org IDs found in file after skipping blanks and comments.",
                file=sys.stderr,
            )
            return 1
    else:
        try:
            all_org_ids = collect_org_ids_from_group(
                base_url, api_key, args.group_id, per_page
            )
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 1
        all_org_ids = sorted(set(all_org_ids))
        if not all_org_ids:
            print("No organizations returned for this group.", file=sys.stderr)
            return 1

    skipped = 0
    cloned = 0
    failed = 0

    for dest in all_org_ids:
        if dest == source_org:
            print(f"Skip source org {dest}")
            skipped += 1
            continue
        body = {"destinationOrgPublicId": dest}
        if dry_run:
            print(f"[dry-run] Would POST clone to org {dest}")
            continue
        print(f"Cloning to org {dest} ...")
        ok, resp_obj, raw = _post_json(
            base_url,
            f"/org/{source_org}/integrations/{integration_id}/clone",
            api_key,
            body,
        )
        if ok:
            if isinstance(resp_obj, dict):
                new_id = resp_obj.get("newIntegrationId")
                if new_id:
                    print(f"  ok — newIntegrationId={new_id}")
                else:
                    print(f"  ok — response: {raw}")
            else:
                print(f"  ok — response: {raw}")
            cloned += 1
        else:
            print(f"  error: {raw[:2000]}", file=sys.stderr)
            failed += 1

    print(
        f"\nDone. cloned={cloned} skipped_source={skipped} failed={failed}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
