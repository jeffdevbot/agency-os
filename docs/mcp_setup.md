# MCP Setup and Verification

This project uses workspace MCP config at:

- `/Users/jeff/code/agency-os/.vscode/mcp.json`

Current expected server names:

- `supabase`

## Expected config

Example `mcp.json`:

```json
{
  "inputs": [],
  "servers": {
    "supabase": {
      "url": "https://mcp.supabase.com/mcp?project_ref=iqkmygvncovwdxagewal"
    }
  }
}
```

## Read-only verification

Run these via MCP `supabase` server using `execute_sql`:

```sql
SELECT now() AS ts;
```

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name
LIMIT 5;
```

Expected result:

- First query returns one timestamp row.
- Second query returns 5 table names.

## Common failure: 401 Unauthorized

If MCP calls return `401 Unauthorized`, the MCP client session is not authenticated yet.

Fix:

1. Re-open MCP/OAuth login flow in the app session.
2. Re-authorize Supabase MCP access.
3. Re-run the two verification queries above.

## Notes

- Keep checks read-only when verifying connectivity.
- If server names are not detected, confirm `.vscode/mcp.json` is loaded by the current workspace and app session.
