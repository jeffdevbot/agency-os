#!/usr/bin/env npx ts-node
/**
 * ClickUp Tasks API test script
 *
 * Usage:
 *   npx ts-node scripts/clickup-tasks.ts lists <space_id>     # List all lists in space
 *   npx ts-node scripts/clickup-tasks.ts create <list_id> <name>  # Create a task
 *   npx ts-node scripts/clickup-tasks.ts subtask <parent_id> <name>  # Create subtask
 */

import * as fs from "fs";
import * as path from "path";

// Read env from frontend-web/.env.local
function loadEnv(): Record<string, string> {
  const possiblePaths = [
    path.join(process.cwd(), "frontend-web/.env.local"),
    path.join(process.cwd(), "../frontend-web/.env.local"),
    path.join(process.cwd(), ".env.local"),
  ];

  let envPath = "";
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) {
      envPath = p;
      break;
    }
  }

  if (!envPath) {
    console.error("Could not find .env.local in:", possiblePaths);
    return {};
  }
  const env: Record<string, string> = {};

  try {
    const content = fs.readFileSync(envPath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIndex = trimmed.indexOf("=");
      if (eqIndex > 0) {
        const key = trimmed.slice(0, eqIndex).trim();
        let value = trimmed.slice(eqIndex + 1).trim();
        if ((value.startsWith('"') && value.endsWith('"')) ||
            (value.startsWith("'") && value.endsWith("'"))) {
          value = value.slice(1, -1);
        }
        env[key] = value;
      }
    }
  } catch (err) {
    console.error("Could not read .env.local:", err);
  }

  return env;
}

const env = loadEnv();
const API_TOKEN = process.env.CLICKUP_API_TOKEN || env.CLICKUP_API_TOKEN;

if (!API_TOKEN) {
  console.error("Error: CLICKUP_API_TOKEN not found in environment or .env.local");
  process.exit(1);
}

const command = process.argv[2];

async function listFolders(spaceId: string): Promise<void> {
  const url = `https://api.clickup.com/api/v2/space/${spaceId}/folder`;
  console.error(`Fetching folders in space ${spaceId}...`);

  const response = await fetch(url, {
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`Error ${response.status}: ${text}`);
    process.exit(1);
  }

  const data = (await response.json()) as { folders: Array<{ id: string; name: string }> };
  console.log("Folders:");
  for (const folder of data.folders ?? []) {
    console.log(`  - ${folder.id}: ${folder.name}`);
  }
}

async function listLists(spaceId: string): Promise<void> {
  // First get folderless lists
  const url = `https://api.clickup.com/api/v2/space/${spaceId}/list`;
  console.error(`Fetching lists in space ${spaceId}...`);

  const response = await fetch(url, {
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`Error ${response.status}: ${text}`);
    process.exit(1);
  }

  const data = (await response.json()) as { lists: Array<{ id: string; name: string; status?: { status: string } }> };
  console.log("Lists (folderless):");
  for (const list of data.lists ?? []) {
    console.log(`  - ${list.id}: ${list.name}`);
  }

  // Also check folders
  await listFolders(spaceId);
}

async function createTask(listId: string, name: string): Promise<string> {
  const url = `https://api.clickup.com/api/v2/list/${listId}/task`;
  console.error(`Creating task "${name}" in list ${listId}...`);

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name,
      markdown_description: "Test task created via API",
      status: "backlog",
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`Error ${response.status}: ${text}`);
    process.exit(1);
  }

  const task = (await response.json()) as { id: string; name: string; url: string };
  console.log(`Created task: ${task.id}`);
  console.log(`  Name: ${task.name}`);
  console.log(`  URL: ${task.url}`);
  return task.id;
}

async function updateTask(taskId: string, name: string, description?: string): Promise<void> {
  const url = `https://api.clickup.com/api/v2/task/${taskId}`;
  console.error(`Updating task ${taskId}...`);

  const body: Record<string, string> = { name };
  if (description) {
    body.description = description;
  }

  const response = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`Error ${response.status}: ${text}`);
    process.exit(1);
  }

  const task = (await response.json()) as { id: string; name: string; url: string };
  console.log(`Updated task: ${task.id}`);
  console.log(`  Name: ${task.name}`);
  console.log(`  URL: ${task.url}`);
}

async function setDescription(taskId: string, description: string): Promise<void> {
  const url = `https://api.clickup.com/api/v2/task/${taskId}`;
  console.error(`Setting description for task ${taskId}...`);

  const response = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ markdown_description: description }),
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`Error ${response.status}: ${text}`);
    process.exit(1);
  }

  const task = (await response.json()) as { id: string; name: string; url: string };
  console.log(`Updated task: ${task.id}`);
  console.log(`  Name: ${task.name}`);
  console.log(`  URL: ${task.url}`);
}

async function assignTask(taskId: string, userId: string): Promise<void> {
  const url = `https://api.clickup.com/api/v2/task/${taskId}`;
  console.error(`Assigning task ${taskId} to user ${userId}...`);

  const response = await fetch(url, {
    method: "PUT",
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      assignees: { add: [parseInt(userId, 10)] },
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`Error ${response.status}: ${text}`);
    process.exit(1);
  }

  const task = (await response.json()) as { id: string; name: string; url: string; assignees: Array<{ username: string }> };
  console.log(`Assigned task: ${task.id}`);
  console.log(`  Name: ${task.name}`);
  console.log(`  Assignees: ${task.assignees.map(a => a.username).join(", ")}`);
  console.log(`  URL: ${task.url}`);
}

async function createSubtask(parentId: string, name: string): Promise<void> {
  // First get the parent task to find its list
  const parentUrl = `https://api.clickup.com/api/v2/task/${parentId}`;
  console.error(`Fetching parent task ${parentId}...`);

  const parentResponse = await fetch(parentUrl, {
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
  });

  if (!parentResponse.ok) {
    const text = await parentResponse.text();
    console.error(`Error ${parentResponse.status}: ${text}`);
    process.exit(1);
  }

  const parentTask = (await parentResponse.json()) as { id: string; list: { id: string } };
  const listId = parentTask.list.id;

  // Create subtask
  const url = `https://api.clickup.com/api/v2/list/${listId}/task`;
  console.error(`Creating subtask "${name}" under parent ${parentId}...`);

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      name,
      markdown_description: "Test subtask created via API",
      parent: parentId,
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`Error ${response.status}: ${text}`);
    process.exit(1);
  }

  const task = (await response.json()) as { id: string; name: string; url: string };
  console.log(`Created subtask: ${task.id}`);
  console.log(`  Name: ${task.name}`);
  console.log(`  URL: ${task.url}`);
}

async function main() {
  if (!command) {
    console.error("Usage:");
    console.error("  npx ts-node scripts/clickup-tasks.ts lists <space_id>        # List all lists");
    console.error("  npx ts-node scripts/clickup-tasks.ts create <list_id> <name> # Create task");
    console.error("  npx ts-node scripts/clickup-tasks.ts subtask <parent_id> <name> # Create subtask");
    console.error("  npx ts-node scripts/clickup-tasks.ts update <task_id> <name>  # Update task name");
    console.error("  npx ts-node scripts/clickup-tasks.ts assign <task_id> <user_id> # Assign task");
    console.error("  echo 'desc' | npx ts-node scripts/clickup-tasks.ts describe <task_id> # Set description from stdin");
    process.exit(1);
  }

  switch (command) {
    case "lists": {
      const spaceId = process.argv[3];
      if (!spaceId) {
        console.error("Usage: npx ts-node scripts/clickup-tasks.ts lists <space_id>");
        process.exit(1);
      }
      await listLists(spaceId);
      break;
    }
    case "create": {
      const listId = process.argv[3];
      const name = process.argv[4];
      if (!listId || !name) {
        console.error("Usage: npx ts-node scripts/clickup-tasks.ts create <list_id> <name>");
        process.exit(1);
      }
      await createTask(listId, name);
      break;
    }
    case "subtask": {
      const parentId = process.argv[3];
      const name = process.argv[4];
      if (!parentId || !name) {
        console.error("Usage: npx ts-node scripts/clickup-tasks.ts subtask <parent_id> <name>");
        process.exit(1);
      }
      await createSubtask(parentId, name);
      break;
    }
    case "update": {
      const taskId = process.argv[3];
      const name = process.argv[4];
      if (!taskId || !name) {
        console.error("Usage: npx ts-node scripts/clickup-tasks.ts update <task_id> <name>");
        process.exit(1);
      }
      await updateTask(taskId, name);
      break;
    }
    case "assign": {
      const taskId = process.argv[3];
      const userId = process.argv[4];
      if (!taskId || !userId) {
        console.error("Usage: npx ts-node scripts/clickup-tasks.ts assign <task_id> <user_id>");
        process.exit(1);
      }
      await assignTask(taskId, userId);
      break;
    }
    case "describe": {
      const taskId = process.argv[3];
      if (!taskId) {
        console.error("Usage: echo 'description' | npx ts-node scripts/clickup-tasks.ts describe <task_id>");
        process.exit(1);
      }
      // Read description from stdin
      const chunks: Buffer[] = [];
      for await (const chunk of process.stdin) {
        chunks.push(chunk);
      }
      const description = Buffer.concat(chunks).toString("utf-8").trim();
      if (!description) {
        console.error("Error: No description provided via stdin");
        process.exit(1);
      }
      await setDescription(taskId, description);
      break;
    }
    default:
      console.error(`Unknown command: ${command}`);
      process.exit(1);
  }
}

main().catch((err) => {
  console.error("Failed:", err);
  process.exit(1);
});
