#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

MCP_SERVER_NAME="${MCP_SERVER_NAME:-supabase}"
TARGET_SCHEMA="${TARGET_SCHEMA:-public}"
OUTPUT_PATH="${OUTPUT_PATH:-docs/db/schema_master.md}"

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: ${command_name}" >&2
    exit 1
  fi
}

require_command codex
require_command python3

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/schema-master.XXXXXX")"
trap 'rm -rf "${TEMP_DIR}"' EXIT

run_query() {
  local output_file="$1"
  local sql_query="$2"
  local jsonl_file="${TEMP_DIR}/query.jsonl"

  codex exec --json --skip-git-repo-check -C "${REPO_ROOT}" \
    "Use MCP server '${MCP_SERVER_NAME}'. Run execute_sql query: ${sql_query}" \
    > "${jsonl_file}"

  python3 - "${jsonl_file}" "${output_file}" <<'PY'
import json
import re
import sys
from pathlib import Path

jsonl_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

payloads = []

for line in jsonl_path.read_text().splitlines():
    if not line.strip():
        continue
    event = json.loads(line)
    if event.get("type") != "item.completed":
        continue
    item = event.get("item", {})
    if item.get("type") != "mcp_tool_call":
        continue
    result = item.get("result") or {}
    content = result.get("content") or []
    for content_item in content:
        text_blob = content_item.get("text")
        if not text_blob:
            continue
        try:
            unwrapped = json.loads(text_blob)
        except Exception:
            continue
        match = re.search(r"<untrusted-data-[^>]+>\n(.*?)\n</untrusted-data-[^>]+>", unwrapped, re.DOTALL)
        if not match:
            continue
        raw_json = match.group(1).strip()
        if not raw_json:
            continue
        parsed = json.loads(raw_json)
        if isinstance(parsed, list):
            payloads.extend(parsed)
        else:
            payloads.append(parsed)

output_path.write_text(json.dumps(payloads))
PY
}

run_query "${TEMP_DIR}/relations.json" "SELECT c.relname AS name, CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'view' WHEN 'm' THEN 'materialized_view' ELSE c.relkind::text END AS type, c.relrowsecurity AS rls_enabled FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = '${TARGET_SCHEMA}' AND c.relkind IN ('r','v','m') ORDER BY c.relkind, c.relname;"

run_query "${TEMP_DIR}/columns.json" "SELECT table_name, ordinal_position, column_name, data_type, udt_name, is_nullable, column_default FROM information_schema.columns WHERE table_schema='${TARGET_SCHEMA}' ORDER BY table_name, ordinal_position;"

run_query "${TEMP_DIR}/primary_keys.json" "SELECT tc.table_name, tc.constraint_name, kcu.column_name, kcu.ordinal_position FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema AND tc.table_name = kcu.table_name WHERE tc.table_schema='${TARGET_SCHEMA}' AND tc.constraint_type='PRIMARY KEY' ORDER BY tc.table_name, kcu.ordinal_position;"

run_query "${TEMP_DIR}/foreign_keys.json" "SELECT tc.table_name, tc.constraint_name, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name, kcu.ordinal_position FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema WHERE tc.table_schema='${TARGET_SCHEMA}' AND tc.constraint_type='FOREIGN KEY' ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position;"

run_query "${TEMP_DIR}/indexes.json" "SELECT tablename AS table_name, indexname AS index_name, indexdef AS index_def FROM pg_indexes WHERE schemaname='${TARGET_SCHEMA}' ORDER BY tablename, indexname;"

run_query "${TEMP_DIR}/policies.json" "SELECT tablename AS table_name, policyname AS policy_name, permissive, roles, cmd, qual, with_check FROM pg_policies WHERE schemaname='${TARGET_SCHEMA}' ORDER BY tablename, policyname;"

run_query "${TEMP_DIR}/functions.json" "SELECT routine_name, routine_type, data_type FROM information_schema.routines WHERE routine_schema='${TARGET_SCHEMA}' ORDER BY routine_name;"

python3 - "${TEMP_DIR}" "${REPO_ROOT}/${OUTPUT_PATH}" "${TARGET_SCHEMA}" <<'PY'
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

temp_dir = Path(sys.argv[1])
output_path = Path(sys.argv[2])
target_schema = sys.argv[3]

relations = json.loads((temp_dir / "relations.json").read_text())
columns = json.loads((temp_dir / "columns.json").read_text())
primary_keys = json.loads((temp_dir / "primary_keys.json").read_text())
foreign_keys = json.loads((temp_dir / "foreign_keys.json").read_text())
indexes = json.loads((temp_dir / "indexes.json").read_text())
policies = json.loads((temp_dir / "policies.json").read_text())
functions = json.loads((temp_dir / "functions.json").read_text())

relations = [item for item in relations if isinstance(item, dict)]
columns = [item for item in columns if isinstance(item, dict)]
primary_keys = [item for item in primary_keys if isinstance(item, dict)]
foreign_keys = [item for item in foreign_keys if isinstance(item, dict)]
indexes = [item for item in indexes if isinstance(item, dict)]
policies = [item for item in policies if isinstance(item, dict)]
functions = [item for item in functions if isinstance(item, dict)]

relations = [item for item in relations if "name" in item and "type" in item]
columns = [item for item in columns if "table_name" in item and "column_name" in item and "ordinal_position" in item]
primary_keys = [item for item in primary_keys if "table_name" in item and "constraint_name" in item and "column_name" in item and "ordinal_position" in item]
foreign_keys = [item for item in foreign_keys if "table_name" in item and "constraint_name" in item and "column_name" in item and "foreign_table_name" in item and "foreign_column_name" in item and "ordinal_position" in item]
indexes = [item for item in indexes if "table_name" in item and "index_name" in item]
policies = [item for item in policies if "table_name" in item and "policy_name" in item and "cmd" in item]
functions = [item for item in functions if "routine_name" in item and "routine_type" in item]

def unique_sort(items, key_fields):
    seen = set()
    result = []

    def normalize(value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def sort_key(item):
        return tuple(normalize(item.get(field)) for field in key_fields)

    for item in items:
        key = tuple(item.get(field) for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return sorted(result, key=sort_key)

relations = unique_sort(relations, ["name", "type"])
columns = unique_sort(columns, ["table_name", "ordinal_position", "column_name"])
primary_keys = unique_sort(primary_keys, ["table_name", "constraint_name", "ordinal_position", "column_name"])
foreign_keys = unique_sort(foreign_keys, ["table_name", "constraint_name", "ordinal_position", "column_name", "foreign_table_name", "foreign_column_name"])
indexes = unique_sort(indexes, ["table_name", "index_name"])
policies = unique_sort(policies, ["table_name", "policy_name", "cmd"])
functions = unique_sort(functions, ["routine_name", "routine_type", "data_type"])

tables = [relation for relation in relations if relation.get("type") == "table"]
views = [relation for relation in relations if relation.get("type") == "view"]
materialized_views = [relation for relation in relations if relation.get("type") == "materialized_view"]

columns_by_table = defaultdict(list)
for column in columns:
    columns_by_table[column["table_name"]].append(column)

primary_keys_by_table = defaultdict(list)
for primary_key in primary_keys:
    primary_keys_by_table[primary_key["table_name"]].append(primary_key)

foreign_keys_by_table = defaultdict(lambda: defaultdict(list))
for foreign_key in foreign_keys:
    foreign_keys_by_table[foreign_key["table_name"]][foreign_key["constraint_name"]].append(foreign_key)

indexes_by_table = defaultdict(list)
for index in indexes:
    indexes_by_table[index["table_name"]].append(index)

policies_by_table = defaultdict(list)
for policy in policies:
    policies_by_table[policy["table_name"]].append(policy)

now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

lines = []
lines.append("# Database Schema Master (Supabase)")
lines.append("")
lines.append("## Snapshot")
lines.append("")
lines.append(f"- Last verified (UTC): `{now_utc}`")
lines.append("- Source: live Supabase introspection via MCP (`supabase.execute_sql`)")
lines.append(f"- Schema: `{target_schema}`")
lines.append(f"- Relations: `{len(relations)}` total (`{len(tables)}` tables, `{len(views)}` views, `{len(materialized_views)}` materialized views)")
lines.append(f"- Columns: `{len(columns)}`")
lines.append(f"- Primary key entries: `{len(primary_keys)}`")
lines.append(f"- Foreign key entries: `{len(foreign_keys)}`")
lines.append(f"- Indexes: `{len(indexes)}`")
lines.append(f"- RLS policies: `{len(policies)}`")
lines.append(f"- Functions: `{len(functions)}`")
lines.append("")
lines.append("## Relations Overview")
lines.append("")
lines.append("| Relation | Type | RLS Enabled |")
lines.append("|---|---|---|")

for relation in sorted(relations, key=lambda relation: relation["name"]):
    rls_enabled = "n/a"
    if relation["type"] == "table":
        rls_enabled = "yes" if relation.get("rls_enabled") else "no"
    lines.append(f"| `{target_schema}.{relation['name']}` | `{relation['type']}` | `{rls_enabled}` |")

lines.append("")
lines.append("## Table Details")
lines.append("")

for table in sorted(tables, key=lambda table: table["name"]):
    table_name = table["name"]
    lines.append(f"### `{target_schema}.{table_name}`")
    lines.append("")
    lines.append(f"- RLS enabled: `{'yes' if table.get('rls_enabled') else 'no'}`")

    primary_key_columns = [entry["column_name"] for entry in sorted(primary_keys_by_table.get(table_name, []), key=lambda entry: entry["ordinal_position"])]
    if primary_key_columns:
        lines.append(f"- Primary key: `{', '.join(primary_key_columns)}`")
    else:
        lines.append("- Primary key: `none`")

    foreign_key_constraints = foreign_keys_by_table.get(table_name, {})
    if foreign_key_constraints:
        foreign_key_parts = []
        for constraint_name in sorted(foreign_key_constraints.keys()):
            parts = sorted(foreign_key_constraints[constraint_name], key=lambda part: part["ordinal_position"])
            source_columns = ", ".join(part["column_name"] for part in parts)
            destination_table = parts[0]["foreign_table_name"]
            destination_columns = ", ".join(part["foreign_column_name"] for part in parts)
            foreign_key_parts.append(f"`{constraint_name}`: ({source_columns}) -> `{target_schema}.{destination_table}`({destination_columns})")
        lines.append("- Foreign keys: " + "; ".join(foreign_key_parts))
    else:
        lines.append("- Foreign keys: `none`")

    table_policies = sorted(policies_by_table.get(table_name, []), key=lambda policy: (policy["policy_name"], policy["cmd"]))
    if table_policies:
        policy_text = "; ".join(f"`{policy['policy_name']}` ({policy['cmd']})" for policy in table_policies)
        lines.append(f"- Policies: {policy_text}")
    else:
        lines.append("- Policies: `none`")

    table_indexes = sorted(indexes_by_table.get(table_name, []), key=lambda index: index["index_name"])
    if table_indexes:
        index_names = ", ".join(f"`{index['index_name']}`" for index in table_indexes)
        lines.append(f"- Indexes ({len(table_indexes)}): {index_names}")
    else:
        lines.append("- Indexes: `none`")

    lines.append("")
    lines.append("| Column | Type | Nullable | Default |")
    lines.append("|---|---|---|---|")
    for column in columns_by_table.get(table_name, []):
        data_type = column["data_type"]
        udt_name = column.get("udt_name")
        type_display = f"{data_type} ({udt_name})" if udt_name and udt_name != data_type else data_type
        nullable = "yes" if column["is_nullable"] == "YES" else "no"
        default_value = column.get("column_default") or ""
        default_value = default_value.replace("|", "\\|")
        lines.append(f"| `{column['column_name']}` | `{type_display}` | `{nullable}` | `{default_value}` |")
    lines.append("")

lines.append(f"## Functions (`{target_schema}` schema)")
lines.append("")
lines.append("| Function | Routine Type | Returns |")
lines.append("|---|---|---|")
for function in sorted(functions, key=lambda function: function["routine_name"]):
    return_type = function.get("data_type") or "n/a"
    lines.append(f"| `{target_schema}.{function['routine_name']}` | `{function['routine_type']}` | `{return_type}` |")

lines.append("")
lines.append("## Maintenance")
lines.append("")
lines.append("- Regenerate this file with `scripts/db/generate-schema-master.sh` after schema changes.")
lines.append("- Treat `supabase/migrations/` + live DB as source of truth; this file is generated documentation.")
lines.append("- If drift is detected, update migrations and docs in the same PR.")

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text("\n".join(lines) + "\n")
PY

echo "Updated ${OUTPUT_PATH}"
