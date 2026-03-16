#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SCHEMAS="${SCHEMAS:-public}"
OUTPUT_PATH="${OUTPUT_PATH:-docs/db/schema_master.md}"
DB_URL="${SUPABASE_DB_URL:-${DATABASE_URL:-}}"
USE_LINKED=1
CHECK_ONLY=0
STDOUT_ONLY=0
KEEP_SQL_DUMP=0
SQL_INPUT=""

usage() {
  cat <<'EOF'
Usage: scripts/db/generate-schema-master.sh [options]

Generate docs/db/schema_master.md from a live Supabase schema dump.

Options:
  --schema <schema[,schema2]>   Schema list to include. Default: public
  --output <path>               Output markdown path. Default: docs/db/schema_master.md
  --db-url <url>                Use this Postgres connection string instead of --linked
  --linked                      Force Supabase CLI linked-project mode (default)
  --sql-input <path>            Parse an existing schema SQL dump instead of fetching one
  --check                       Exit non-zero if generated output differs from --output
  --stdout                      Print markdown to stdout instead of writing a file
  --keep-sql-dump               Keep the fetched SQL dump in the temp directory for debugging
  -h, --help                    Show this help message

Environment:
  SUPABASE_DB_URL / DATABASE_URL
    Alternate way to provide the remote Postgres connection string.
EOF
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: ${command_name}" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --schema)
      [[ $# -ge 2 ]] || { echo "Missing value for --schema" >&2; exit 1; }
      SCHEMAS="$2"
      shift 2
      ;;
    --output)
      [[ $# -ge 2 ]] || { echo "Missing value for --output" >&2; exit 1; }
      OUTPUT_PATH="$2"
      shift 2
      ;;
    --db-url)
      [[ $# -ge 2 ]] || { echo "Missing value for --db-url" >&2; exit 1; }
      DB_URL="$2"
      USE_LINKED=0
      shift 2
      ;;
    --linked)
      USE_LINKED=1
      shift
      ;;
    --sql-input)
      [[ $# -ge 2 ]] || { echo "Missing value for --sql-input" >&2; exit 1; }
      SQL_INPUT="$2"
      shift 2
      ;;
    --check)
      CHECK_ONLY=1
      shift
      ;;
    --stdout)
      STDOUT_ONLY=1
      shift
      ;;
    --keep-sql-dump)
      KEEP_SQL_DUMP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

require_command supabase
require_command python3

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/schema-master.XXXXXX")"
cleanup() {
  if [[ "${KEEP_SQL_DUMP}" -eq 1 ]]; then
    echo "Kept temp dir: ${TEMP_DIR}" >&2
    return
  fi
  rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

DUMP_PATH="${TEMP_DIR}/schema.sql"
GENERATED_PATH="${TEMP_DIR}/schema_master.md"

if [[ -n "${SQL_INPUT}" ]]; then
  cp "${SQL_INPUT}" "${DUMP_PATH}"
else
  DUMP_ARGS=(db dump --schema "${SCHEMAS}" --keep-comments --file "${DUMP_PATH}")
  if [[ -n "${DB_URL}" ]]; then
    DUMP_ARGS+=(--db-url "${DB_URL}")
  elif [[ "${USE_LINKED}" -eq 1 ]]; then
    DUMP_ARGS+=(--linked)
  else
    echo "Either provide --db-url / SUPABASE_DB_URL / DATABASE_URL or use --linked." >&2
    exit 1
  fi
  supabase "${DUMP_ARGS[@]}"
fi

python3 - "${DUMP_PATH}" "${GENERATED_PATH}" "${SCHEMAS}" <<'PY'
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

dump_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
schemas_csv = sys.argv[3]
target_schemas = [schema.strip() for schema in schemas_csv.split(",") if schema.strip()]

sql_text = dump_path.read_text()


def split_statements(text: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    i = 0
    quote: str | None = None
    dollar_tag: str | None = None
    line_comment = False
    block_comment = False
    while i < len(text):
        chunk = text[i:]
        if line_comment:
            char = text[i]
            buffer.append(char)
            if char == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if chunk.startswith("*/"):
                buffer.append("*/")
                i += 2
                block_comment = False
            else:
                buffer.append(text[i])
                i += 1
            continue
        if dollar_tag is not None:
            if chunk.startswith(dollar_tag):
                buffer.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buffer.append(text[i])
                i += 1
            continue
        if quote is not None:
            char = text[i]
            buffer.append(char)
            if quote == "'" and char == "'" and i + 1 < len(text) and text[i + 1] == "'":
                buffer.append("'")
                i += 2
                continue
            if char == quote:
                quote = None
            i += 1
            continue
        if chunk.startswith("--"):
            buffer.append("--")
            i += 2
            line_comment = True
            continue
        if chunk.startswith("/*"):
            buffer.append("/*")
            i += 2
            block_comment = True
            continue
        if text[i] in ("'", '"'):
            quote = text[i]
            buffer.append(text[i])
            i += 1
            continue
        dollar_match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", chunk)
        if dollar_match:
            dollar_tag = dollar_match.group(0)
            buffer.append(dollar_tag)
            i += len(dollar_tag)
            continue
        if text[i] == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            i += 1
            continue
        buffer.append(text[i])
        i += 1
    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def strip_sql_comments(statement: str) -> str:
    cleaned_lines: list[str] = []
    for line in statement.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.S)
    return cleaned.strip()


def normalize_ident(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('""', '"')
    return value


def parse_qualified_name(raw: str) -> tuple[str | None, str]:
    cleaned = raw.strip()
    if cleaned.upper().startswith("ONLY "):
        cleaned = cleaned[5:].strip()
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    i = 0
    while i < len(cleaned):
        char = cleaned[i]
        if char == '"':
            in_quotes = not in_quotes
            current.append(char)
            i += 1
            continue
        if char == "." and not in_quotes:
            parts.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(char)
        i += 1
    if current:
        parts.append("".join(current).strip())
    if len(parts) == 1:
        return None, normalize_ident(parts[0])
    return normalize_ident(parts[0]), normalize_ident(parts[1])


def split_top_level(text: str, delimiter: str = ",") -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    dollar_tag: str | None = None
    i = 0
    while i < len(text):
        chunk = text[i:]
        if dollar_tag is not None:
            if chunk.startswith(dollar_tag):
                current.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                current.append(text[i])
                i += 1
            continue
        if quote is not None:
            char = text[i]
            current.append(char)
            if quote == "'" and char == "'" and i + 1 < len(text) and text[i + 1] == "'":
                current.append("'")
                i += 2
                continue
            if char == quote:
                quote = None
            i += 1
            continue
        if text[i] in ("'", '"'):
            quote = text[i]
            current.append(text[i])
            i += 1
            continue
        dollar_match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", chunk)
        if dollar_match:
            dollar_tag = dollar_match.group(0)
            current.append(dollar_tag)
            i += len(dollar_tag)
            continue
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == delimiter and depth == 0:
            parts.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(char)
        i += 1
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def top_level_keyword_index(text: str, keyword: str) -> int:
    depth = 0
    quote: str | None = None
    dollar_tag: str | None = None
    upper_text = text.upper()
    upper_keyword = keyword.upper()
    i = 0
    while i < len(text):
        chunk = text[i:]
        if dollar_tag is not None:
            if chunk.startswith(dollar_tag):
                i += len(dollar_tag)
                dollar_tag = None
            else:
                i += 1
            continue
        if quote is not None:
            if text[i] == quote:
                if quote == "'" and i + 1 < len(text) and text[i + 1] == "'":
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if text[i] in ("'", '"'):
            quote = text[i]
            i += 1
            continue
        dollar_match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", chunk)
        if dollar_match:
            dollar_tag = dollar_match.group(0)
            i += len(dollar_tag)
            continue
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if depth == 0 and upper_text.startswith(upper_keyword, i):
            prev_char = upper_text[i - 1] if i > 0 else " "
            next_index = i + len(upper_keyword)
            next_char = upper_text[next_index] if next_index < len(upper_text) else " "
            if not (prev_char.isalnum() or prev_char == "_") and not (
                next_char.isalnum() or next_char == "_"
            ):
                return i
        i += 1
    return -1


def parse_column_definition(definition: str) -> dict | None:
    raw = definition.strip()
    if not raw:
        return None
    if re.match(r"^(CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK)\b", raw, flags=re.I):
        return None
    if raw.startswith('"'):
        end = 1
        while end < len(raw):
            if raw[end] == '"' and raw[end - 1] != "\\":
                break
            end += 1
        column_name = normalize_ident(raw[: end + 1])
        remainder = raw[end + 1 :].strip()
    else:
        parts = raw.split(None, 1)
        if len(parts) < 2:
            return None
        column_name, remainder = parts[0], parts[1]
        column_name = normalize_ident(column_name)

    cut_points = [
        idx
        for idx in (
            top_level_keyword_index(remainder, "DEFAULT"),
            top_level_keyword_index(remainder, "NOT NULL"),
            top_level_keyword_index(remainder, "NULL"),
            top_level_keyword_index(remainder, "COLLATE"),
            top_level_keyword_index(remainder, "CONSTRAINT"),
            top_level_keyword_index(remainder, "CHECK"),
            top_level_keyword_index(remainder, "REFERENCES"),
            top_level_keyword_index(remainder, "GENERATED"),
        )
        if idx >= 0
    ]
    type_end = min(cut_points) if cut_points else len(remainder)
    type_name = remainder[:type_end].strip()
    default_value = ""
    default_index = top_level_keyword_index(remainder, "DEFAULT")
    if default_index >= 0:
        default_tail = remainder[default_index + len("DEFAULT") :].strip()
        next_keywords = [
            idx
            for idx in (
                top_level_keyword_index(default_tail, "NOT NULL"),
                top_level_keyword_index(default_tail, "NULL"),
                top_level_keyword_index(default_tail, "COLLATE"),
                top_level_keyword_index(default_tail, "CONSTRAINT"),
                top_level_keyword_index(default_tail, "CHECK"),
                top_level_keyword_index(default_tail, "REFERENCES"),
                top_level_keyword_index(default_tail, "GENERATED"),
            )
            if idx >= 0
        ]
        default_end = min(next_keywords) if next_keywords else len(default_tail)
        default_value = default_tail[:default_end].strip()
    nullable = top_level_keyword_index(remainder, "NOT NULL") < 0
    return {
        "column_name": column_name,
        "data_type": type_name or "unknown",
        "is_nullable": nullable,
        "column_default": default_value,
    }


def parse_columns_from_body(body: str) -> list[dict]:
    columns: list[dict] = []
    for item in split_top_level(body):
        column = parse_column_definition(item)
        if column is not None:
            columns.append(column)
    return columns


def extract_inline_primary_key(definition: str) -> list[str]:
    match = re.search(r"PRIMARY\s+KEY\s*\((.*?)\)", definition, flags=re.I | re.S)
    if not match:
        return []
    return [normalize_ident(part) for part in split_top_level(match.group(1))]


def extract_inline_foreign_key(definition: str) -> dict | None:
    match = re.search(
        r"(?:CONSTRAINT\s+([^\s]+)\s+)?FOREIGN\s+KEY\s*\((.*?)\)\s+REFERENCES\s+([^\s(]+)\s*\((.*?)\)",
        definition,
        flags=re.I | re.S,
    )
    if not match:
        return None
    _, source_cols, foreign_table_raw, foreign_cols = match.groups()
    foreign_schema, foreign_table = parse_qualified_name(foreign_table_raw)
    return {
        "source_columns": [normalize_ident(part) for part in split_top_level(source_cols)],
        "foreign_schema": foreign_schema,
        "foreign_table": foreign_table,
        "foreign_columns": [normalize_ident(part) for part in split_top_level(foreign_cols)],
    }


relations: dict[tuple[str, str], dict] = {}
table_columns: dict[tuple[str, str], list[dict]] = defaultdict(list)
primary_keys: dict[tuple[str, str], list[str]] = {}
foreign_keys: dict[tuple[str, str], list[dict]] = defaultdict(list)
indexes: dict[tuple[str, str], list[dict]] = defaultdict(list)
policies: dict[tuple[str, str], list[dict]] = defaultdict(list)
functions: list[dict] = []

statements = [strip_sql_comments(statement) for statement in split_statements(sql_text)]

for statement in statements:
    if not statement:
        continue

    create_table = re.match(
        r'^CREATE TABLE\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s*\((.*)\)$',
        statement,
        flags=re.I | re.S,
    )
    if create_table:
        schema_name, relation_name = parse_qualified_name(create_table.group(1))
        if schema_name and schema_name not in target_schemas:
            continue
        schema_name = schema_name or target_schemas[0]
        key = (schema_name, relation_name)
        relations[key] = {
            "schema": schema_name,
            "name": relation_name,
            "type": "table",
            "rls_enabled": False,
        }
        body = create_table.group(2)
        table_columns[key] = parse_columns_from_body(body)
        for item in split_top_level(body):
            if re.match(r"^(CONSTRAINT\s+[^\s]+\s+)?PRIMARY\s+KEY\b", item, flags=re.I):
                primary_keys[key] = extract_inline_primary_key(item)
            elif re.match(r"^(CONSTRAINT\s+[^\s]+\s+)?FOREIGN\s+KEY\b", item, flags=re.I):
                foreign_key = extract_inline_foreign_key(item)
                if foreign_key:
                    foreign_keys[key].append(foreign_key)
        continue

    create_view = re.match(
        r'^CREATE (MATERIALIZED )?VIEW\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s+AS\b',
        statement,
        flags=re.I | re.S,
    )
    if create_view:
        materialized = bool(create_view.group(1))
        schema_name, relation_name = parse_qualified_name(create_view.group(2))
        if schema_name and schema_name not in target_schemas:
            continue
        schema_name = schema_name or target_schemas[0]
        relations[(schema_name, relation_name)] = {
            "schema": schema_name,
            "name": relation_name,
            "type": "materialized_view" if materialized else "view",
            "rls_enabled": None,
        }
        continue

    alter_pk = re.match(
        r'^ALTER TABLE(?: ONLY)?\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s+ADD CONSTRAINT\s+[^\s]+\s+PRIMARY KEY\s*\((.*?)\)$',
        statement,
        flags=re.I | re.S,
    )
    if alter_pk:
        schema_name, relation_name = parse_qualified_name(alter_pk.group(1))
        if schema_name and schema_name not in target_schemas:
            continue
        schema_name = schema_name or target_schemas[0]
        primary_keys[(schema_name, relation_name)] = [
            normalize_ident(part) for part in split_top_level(alter_pk.group(2))
        ]
        continue

    alter_fk = re.match(
        r'^ALTER TABLE(?: ONLY)?\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s+ADD CONSTRAINT\s+[^\s]+\s+FOREIGN KEY\s*\((.*?)\)\s+REFERENCES\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s*\((.*?)\)$',
        statement,
        flags=re.I | re.S,
    )
    if alter_fk:
        schema_name, relation_name = parse_qualified_name(alter_fk.group(1))
        if schema_name and schema_name not in target_schemas:
            continue
        schema_name = schema_name or target_schemas[0]
        foreign_schema, foreign_table = parse_qualified_name(alter_fk.group(3))
        foreign_keys[(schema_name, relation_name)].append(
            {
                "source_columns": [normalize_ident(part) for part in split_top_level(alter_fk.group(2))],
                "foreign_schema": foreign_schema or schema_name,
                "foreign_table": foreign_table,
                "foreign_columns": [normalize_ident(part) for part in split_top_level(alter_fk.group(4))],
            }
        )
        continue

    create_index = re.match(
        r'^CREATE (?:UNIQUE )?INDEX\s+("?[\w$]+"?)\s+ON\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s+(.*)$',
        statement,
        flags=re.I | re.S,
    )
    if create_index:
        index_name = normalize_ident(create_index.group(1))
        schema_name, relation_name = parse_qualified_name(create_index.group(2))
        if schema_name and schema_name not in target_schemas:
            continue
        schema_name = schema_name or target_schemas[0]
        indexes[(schema_name, relation_name)].append(
            {"index_name": index_name, "index_def": " ".join(statement.split())}
        )
        continue

    rls_enable = re.match(
        r'^ALTER TABLE(?: ONLY)?\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s+ENABLE ROW LEVEL SECURITY$',
        statement,
        flags=re.I,
    )
    if rls_enable:
        schema_name, relation_name = parse_qualified_name(rls_enable.group(1))
        if schema_name and schema_name not in target_schemas:
            continue
        schema_name = schema_name or target_schemas[0]
        key = (schema_name, relation_name)
        relations.setdefault(
            key,
            {"schema": schema_name, "name": relation_name, "type": "table", "rls_enabled": False},
        )
        relations[key]["rls_enabled"] = True
        continue

    create_policy = re.match(
        r'^CREATE POLICY\s+("?[\w$]+"?)\s+ON\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s*(.*)$',
        statement,
        flags=re.I | re.S,
    )
    if create_policy:
        policy_name = normalize_ident(create_policy.group(1))
        schema_name, relation_name = parse_qualified_name(create_policy.group(2))
        if schema_name and schema_name not in target_schemas:
            continue
        schema_name = schema_name or target_schemas[0]
        tail = create_policy.group(3)
        cmd_match = re.search(r"\bFOR\s+([A-Z ]+?)(?:\bTO\b|\bUSING\b|\bWITH\b|$)", tail, flags=re.I)
        cmd = cmd_match.group(1).strip().lower() if cmd_match else "all"
        policies[(schema_name, relation_name)].append(
            {
                "policy_name": policy_name,
                "cmd": cmd,
            }
        )
        continue

    create_function = re.match(
        r'^CREATE(?: OR REPLACE)? FUNCTION\s+("?[\w$]+"?(?:\."?[\w$]+"?)?)\s*\((.*)$',
        statement,
        flags=re.I | re.S,
    )
    if create_function:
        schema_name, function_name = parse_qualified_name(create_function.group(1))
        if schema_name and schema_name not in target_schemas:
            continue
        schema_name = schema_name or target_schemas[0]
        returns_match = re.search(r"\bRETURNS\s+(.+?)\bLANGUAGE\b", statement, flags=re.I | re.S)
        functions.append(
            {
                "schema": schema_name,
                "routine_name": function_name,
                "routine_type": "FUNCTION",
                "data_type": " ".join(returns_match.group(1).split()) if returns_match else "n/a",
            }
        )
        continue

relations_list = sorted(
    relations.values(),
    key=lambda item: (item["schema"], item["name"]),
)
tables = [item for item in relations_list if item["type"] == "table"]
views = [item for item in relations_list if item["type"] == "view"]
materialized_views = [item for item in relations_list if item["type"] == "materialized_view"]

column_count = sum(len(table_columns[(table["schema"], table["name"])]) for table in tables)
primary_key_count = sum(1 for columns in primary_keys.values() if columns)
foreign_key_count = sum(len(items) for items in foreign_keys.values())
index_count = sum(len(items) for items in indexes.values())
policy_count = sum(len(items) for items in policies.values())
functions = sorted(functions, key=lambda item: (item["schema"], item["routine_name"]))
now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

lines: list[str] = []
lines.append("# Database Schema Master (Supabase)")
lines.append("")
lines.append("## Snapshot")
lines.append("")
lines.append(f"- Last verified (UTC): `{now_utc}`")
lines.append("- Source: live schema SQL from `supabase db dump`")
lines.append(f"- Schemas: `{', '.join(target_schemas)}`")
lines.append(
    f"- Relations: `{len(relations_list)}` total (`{len(tables)}` tables, "
    f"`{len(views)}` views, `{len(materialized_views)}` materialized views)"
)
lines.append(f"- Columns: `{column_count}`")
lines.append(f"- Tables with primary keys: `{primary_key_count}`")
lines.append(f"- Foreign keys: `{foreign_key_count}`")
lines.append(f"- Indexes: `{index_count}`")
lines.append(f"- RLS policies: `{policy_count}`")
lines.append(f"- Functions: `{len(functions)}`")
lines.append("")
lines.append("## Relations Overview")
lines.append("")
lines.append("| Relation | Type | RLS Enabled |")
lines.append("|---|---|---|")
for relation in relations_list:
    if relation["type"] == "table":
        rls = "yes" if relation.get("rls_enabled") else "no"
    else:
        rls = "n/a"
    lines.append(
        f"| `{relation['schema']}.{relation['name']}` | `{relation['type']}` | `{rls}` |"
    )

lines.append("")
lines.append("## Table Details")
lines.append("")
for table in tables:
    key = (table["schema"], table["name"])
    lines.append(f"### `{table['schema']}.{table['name']}`")
    lines.append("")
    lines.append(f"- RLS enabled: `{'yes' if table.get('rls_enabled') else 'no'}`")
    pk_columns = primary_keys.get(key, [])
    if pk_columns:
        lines.append(f"- Primary key: `{', '.join(pk_columns)}`")
    else:
        lines.append("- Primary key: `none`")
    fk_items = foreign_keys.get(key, [])
    if fk_items:
        fk_text = "; ".join(
            f"({', '.join(item['source_columns'])}) -> "
            f"`{item['foreign_schema']}.{item['foreign_table']}`"
            f"({', '.join(item['foreign_columns'])})"
            for item in fk_items
        )
        lines.append(f"- Foreign keys: {fk_text}")
    else:
        lines.append("- Foreign keys: `none`")
    policy_items = policies.get(key, [])
    if policy_items:
        policy_text = "; ".join(
            f"`{item['policy_name']}` ({item['cmd']})" for item in policy_items
        )
        lines.append(f"- Policies: {policy_text}")
    else:
        lines.append("- Policies: `none`")
    index_items = indexes.get(key, [])
    if index_items:
        index_text = ", ".join(f"`{item['index_name']}`" for item in index_items)
        lines.append(f"- Indexes ({len(index_items)}): {index_text}")
    else:
        lines.append("- Indexes: `none`")
    lines.append("")
    lines.append("| Column | Type | Nullable | Default |")
    lines.append("|---|---|---|---|")
    for column in table_columns.get(key, []):
        default_value = column["column_default"].replace("|", "\\|")
        nullable = "yes" if column["is_nullable"] else "no"
        lines.append(
            f"| `{column['column_name']}` | `{column['data_type']}` | "
            f"`{nullable}` | `{default_value}` |"
        )
    lines.append("")

lines.append("## Functions")
lines.append("")
lines.append("| Function | Routine Type | Returns |")
lines.append("|---|---|---|")
for function in functions:
    lines.append(
        f"| `{function['schema']}.{function['routine_name']}` | "
        f"`{function['routine_type']}` | `{function['data_type']}` |"
    )

lines.append("")
lines.append("## Maintenance")
lines.append("")
lines.append(
    "- Regenerate this file with "
    "`scripts/db/generate-schema-master.sh --linked` or "
    "`scripts/db/generate-schema-master.sh --db-url \"$SUPABASE_DB_URL\"`."
)
lines.append(
    "- Use `scripts/db/generate-schema-master.sh --check` in CI or before commit "
    "to catch schema doc drift."
)
lines.append("- Treat `supabase/migrations/` + live DB as source of truth; this file is generated documentation.")

output_path.write_text("\n".join(lines) + "\n")
PY

if [[ "${STDOUT_ONLY}" -eq 1 ]]; then
  cat "${GENERATED_PATH}"
  exit 0
fi

ABS_OUTPUT_PATH="${REPO_ROOT}/${OUTPUT_PATH}"

if [[ "${CHECK_ONLY}" -eq 1 ]]; then
  if [[ ! -f "${ABS_OUTPUT_PATH}" ]]; then
    echo "Schema master missing: ${OUTPUT_PATH}" >&2
    exit 1
  fi
  if ! cmp -s "${GENERATED_PATH}" "${ABS_OUTPUT_PATH}"; then
    echo "Schema master drift detected: ${OUTPUT_PATH}" >&2
    diff -u "${ABS_OUTPUT_PATH}" "${GENERATED_PATH}" || true
    exit 1
  fi
  echo "Schema master is up to date: ${OUTPUT_PATH}"
  exit 0
fi

mkdir -p "$(dirname "${ABS_OUTPUT_PATH}")"
cp "${GENERATED_PATH}" "${ABS_OUTPUT_PATH}"
echo "Updated ${OUTPUT_PATH}"
