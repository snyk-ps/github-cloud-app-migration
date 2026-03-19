#!/usr/bin/env bash
#
# Clone a GitHub Cloud App org integration from a source Snyk Organization to every
# other Organization in a Snyk Group using the v1 Integrations API.
#
# Required environment:
#   SNYK_API_KEY         Personal or service API token (Authorization: token …)
#   SNYK_SOURCE_ORG_ID   Org that already has the GitHub Cloud App integration
#   SNYK_GROUP_ID        Required unless SNYK_TARGET_ORG_IDS_FILE is set — group whose orgs receive the clone
#
# Optional environment:
#   SNYK_TARGET_ORG_IDS_FILE  If set, path to a file of destination org public IDs (one per line).
#                             Blank lines and lines starting with # are ignored. Whitespace is trimmed.
#                             When set, orgs are taken only from this file (no GET /group/.../orgs).
#   SNYK_API_BASE         Default: https://api.snyk.io/v1 (set for other regions, e.g. https://api.eu.snyk.io/v1)
#   SNYK_INTEGRATION_TYPE Default: github-cloud-app (path segment for GET integration-by-type)
#   SNYK_INTEGRATION_ID   If set, skip lookup; must be the integration public ID in the source org
#   SNYK_DRY_RUN          If 1, only print planned actions
#   SNYK_PER_PAGE         Default: 100 (max per v1 spec)
#
# Dependencies: curl, jq
#
# API reference:
#   https://docs.snyk.io/snyk-api/reference/integrations-v1
#   https://docs.snyk.io/snyk-api/reference/groups-v1

set -euo pipefail

readonly SNYK_API_BASE="${SNYK_API_BASE:-https://api.snyk.io/v1}"
readonly SNYK_INTEGRATION_TYPE="${SNYK_INTEGRATION_TYPE:-github-cloud-app}"
readonly SNYK_PER_PAGE="${SNYK_PER_PAGE:-100}"
readonly SNYK_DRY_RUN="${SNYK_DRY_RUN:-1}"

die() {
  printf '%s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

snyk_get() {
  local path="$1"
  curl -sS -f \
    -H "Authorization: token ${SNYK_API_KEY}" \
    -H "Content-Type: application/json" \
    "${SNYK_API_BASE}${path}"
}

snyk_post_json() {
  local path="$1"
  local body="$2"
  curl -sS -f \
    -X POST \
    -H "Authorization: token ${SNYK_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$body" \
    "${SNYK_API_BASE}${path}"
}

require_cmd curl
require_cmd jq

[[ -n "${SNYK_API_KEY:-}" ]] || die "SNYK_API_KEY is not set."
[[ -n "${SNYK_SOURCE_ORG_ID:-}" ]] || die "SNYK_SOURCE_ORG_ID is not set."
if [[ -z "${SNYK_TARGET_ORG_IDS_FILE:-}" ]]; then
  [[ -n "${SNYK_GROUP_ID:-}" ]] || die "SNYK_GROUP_ID is not set (or set SNYK_TARGET_ORG_IDS_FILE to supply destination org IDs)."
fi

integration_id="${SNYK_INTEGRATION_ID:-}"
if [[ -z "$integration_id" ]]; then
  printf 'Resolving integration id for type %q in source org %s...\n' "$SNYK_INTEGRATION_TYPE" "$SNYK_SOURCE_ORG_ID"
  int_json="$(snyk_get "/org/${SNYK_SOURCE_ORG_ID}/integrations/${SNYK_INTEGRATION_TYPE}")" || {
    die "Failed to GET integration by type. Ensure the source org has ${SNYK_INTEGRATION_TYPE} configured and your token has View Integrations."
  }
  integration_id="$(printf '%s' "$int_json" | jq -r '.id // empty')"
  [[ -n "$integration_id" ]] || die "Could not read .id from integration response."
  printf 'Using integration id: %s\n' "$integration_id"
else
  printf 'Using SNYK_INTEGRATION_ID: %s\n' "$integration_id"
fi

collect_org_ids_from_group() {
  local offset=0
  while true; do
    local resp
    resp="$(snyk_get "/group/${SNYK_GROUP_ID}/orgs?perPage=${SNYK_PER_PAGE}&page=${offset}")" || {
      die "Failed to list orgs for group ${SNYK_GROUP_ID}. Check SNYK_GROUP_ID and group list permissions."
    }
    local batch
    batch="$(printf '%s' "$resp" | jq -c '.orgs // []')"
    local n
    n="$(printf '%s' "$batch" | jq 'length')"
    if [[ "$n" -eq 0 ]]; then
      break
    fi
    printf '%s' "$batch" | jq -r '.[].id'
    if [[ "$n" -lt "$SNYK_PER_PAGE" ]]; then
      break
    fi
    offset=$((offset + SNYK_PER_PAGE))
  done
}

# Trim leading and trailing whitespace (POSIX character class).
trim_space() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

collect_org_ids_from_file() {
  local path="$1"
  [[ -f "$path" ]] || die "SNYK_TARGET_ORG_IDS_FILE is not a regular file: $path"
  [[ -r "$path" ]] || die "SNYK_TARGET_ORG_IDS_FILE is not readable: $path"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(trim_space "$line")"
    [[ -z "$line" ]] && continue
    [[ "$line" == \#* ]] && continue
    printf '%s\n' "$line"
  done < "$path"
}

all_org_ids=()
if [[ -n "${SNYK_TARGET_ORG_IDS_FILE:-}" ]]; then
  printf 'Loading destination org IDs from %q\n' "$SNYK_TARGET_ORG_IDS_FILE"
  while IFS= read -r oid; do
    [[ -n "$oid" ]] && all_org_ids+=("$oid")
  done < <(collect_org_ids_from_file "$SNYK_TARGET_ORG_IDS_FILE" | sort -u)
  [[ ${#all_org_ids[@]} -gt 0 ]] || die "No org IDs found in SNYK_TARGET_ORG_IDS_FILE after skipping blanks and comments."
else
  while IFS= read -r oid; do
    [[ -n "$oid" ]] && all_org_ids+=("$oid")
  done < <(collect_org_ids_from_group | sort -u)
  [[ ${#all_org_ids[@]} -gt 0 ]] || die "No organizations returned for this group."
fi

skipped=0
cloned=0
failed=0

for dest in "${all_org_ids[@]}"; do
  if [[ "$dest" == "$SNYK_SOURCE_ORG_ID" ]]; then
    printf 'Skip source org %s\n' "$dest"
    ((skipped += 1)) || true
    continue
  fi

  body="$(jq -nc --arg id "$dest" '{destinationOrgPublicId: $id}')"
  if [[ "$SNYK_DRY_RUN" == "1" ]]; then
    printf '[dry-run] Would POST clone to org %s\n' "$dest"
    continue
  fi

  printf 'Cloning to org %s ...\n' "$dest"
  if out="$(snyk_post_json "/org/${SNYK_SOURCE_ORG_ID}/integrations/${integration_id}/clone" "$body" 2>&1)"; then
    new_id="$(printf '%s' "$out" | jq -r '.newIntegrationId // empty')"
    if [[ -n "$new_id" ]]; then
      printf '  ok — newIntegrationId=%s\n' "$new_id"
    else
      printf '  ok — response: %s\n' "$out"
    fi
    ((cloned += 1)) || true
  else
    printf '  error: %s\n' "$out" >&2
    ((failed += 1)) || true
  fi
done

printf '\nDone. cloned=%s skipped_source=%s failed=%s\n' "$cloned" "$skipped" "$failed"
[[ "$failed" -eq 0 ]]
