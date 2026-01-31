#!/usr/bin/env npx ts-node
/**
 * Fetch a ClickUp Doc and output its content as markdown.
 *
 * Usage:
 *   npx ts-node scripts/fetch-clickup-doc.ts <doc_id>
 *
 * The doc_id can be found in the ClickUp doc URL:
 *   https://app.clickup.com/1234567/v/dc/abcd-123/efgh-456
 *                                      ^^^^^^^^  ^^^^^^^^
 *                                      workspace  doc_id
 *
 * Requires CLICKUP_API_TOKEN in frontend-web/.env.local
 */

import * as fs from "fs";
import * as path from "path";

// Read env from frontend-web/.env.local
function loadEnv(): Record<string, string> {
  // Try multiple paths to find .env.local
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
        // Remove quotes if present
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
const WORKSPACE_ID = process.env.CLICKUP_TEAM_ID || env.CLICKUP_TEAM_ID || "42600885";

if (!API_TOKEN) {
  console.error("Error: CLICKUP_API_TOKEN not found in environment or .env.local");
  process.exit(1);
}

const docId = process.argv[2];

if (!docId) {
  console.error("Usage:");
  console.error("  npx ts-node scripts/fetch-clickup-doc.ts list              # List all docs");
  console.error("  npx ts-node scripts/fetch-clickup-doc.ts <doc_id>          # Fetch doc pages");
  console.error("  npx ts-node scripts/fetch-clickup-doc.ts <doc_id>/<page_id> # Fetch specific page");
  console.error("");
  console.error("URL format: https://app.clickup.com/WORKSPACE/docs/DOC_ID/PAGE_ID");
  process.exit(1);
}

// Parse doc_id and optional page_id
const [parsedDocId, pageId] = docId.includes("/") ? docId.split("/") : [docId, null];

interface ClickUpPage {
  id: string;
  name: string;
  content?: string;
  orderindex?: number;
  pages?: ClickUpPage[];
}

interface ClickUpDocResponse {
  id: string;
  name: string;
  pages?: ClickUpPage[];
}

async function listDocs(): Promise<void> {
  // List all docs in workspace using v3 API
  const url = `https://api.clickup.com/api/v3/workspaces/${WORKSPACE_ID}/docs`;

  console.error(`Listing docs in workspace ${WORKSPACE_ID}...`);

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

  const data = (await response.json()) as { docs?: Array<{ id: string; name: string }> };
  console.log("Available docs:");
  for (const doc of data.docs ?? []) {
    console.log(`  - ${doc.id}: ${doc.name}`);
  }
}

async function fetchPage(docId: string, pageId: string): Promise<void> {
  const url = `https://api.clickup.com/api/v3/workspaces/${WORKSPACE_ID}/docs/${docId}/pages/${pageId}`;
  console.error(`Fetching page: ${docId}/${pageId}...`);

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

  const page = (await response.json()) as ClickUpPage;
  console.error(`Page name: "${page.name}"`);
  console.error("---");
  console.error("");

  console.log(`# ${page.name}`);
  console.log("");
  if (page.content) {
    console.log(page.content);
  } else {
    console.log("(No content)");
  }
}

async function fetchDocPages(docId: string): Promise<void> {
  // First get doc info
  const infoUrl = `https://api.clickup.com/api/v3/workspaces/${WORKSPACE_ID}/docs/${docId}`;
  console.error(`Fetching doc info: ${docId}...`);

  const infoResponse = await fetch(infoUrl, {
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
  });

  if (!infoResponse.ok) {
    const text = await infoResponse.text();
    console.error(`Error ${infoResponse.status}: ${text}`);
    process.exit(1);
  }

  const docInfo = (await infoResponse.json()) as {
    id: string;
    name: string;
    content?: string;
    pages?: ClickUpPage[];
  };

  console.error(`Doc name: "${docInfo.name}"`);

  // Check if content is directly on the doc
  if (docInfo.content) {
    console.log(`# ${docInfo.name}`);
    console.log("");
    console.log(docInfo.content);
    return;
  }

  // Check if pages are included in doc info
  if (docInfo.pages && docInfo.pages.length > 0) {
    console.error(`Found ${docInfo.pages.length} pages in doc info`);
    console.log(`# ${docInfo.name}`);
    console.log("");
    for (const page of docInfo.pages) {
      outputPage(page, 2);
    }
    return;
  }

  // Try the pages endpoint
  const pagesUrl = `https://api.clickup.com/api/v3/workspaces/${WORKSPACE_ID}/docs/${docId}/pages`;
  console.error(`Fetching pages from separate endpoint...`);

  const pagesResponse = await fetch(pagesUrl, {
    headers: {
      Authorization: API_TOKEN!,
      "Content-Type": "application/json",
    },
  });

  if (!pagesResponse.ok) {
    const text = await pagesResponse.text();
    console.error(`Pages error ${pagesResponse.status}: ${text}`);
    // Don't exit, try to output what we have
  } else {
    const pagesData = (await pagesResponse.json()) as { pages?: ClickUpPage[] };
    if (pagesData.pages && pagesData.pages.length > 0) {
      console.error(`Found ${pagesData.pages.length} pages`);
      console.log(`# ${docInfo.name}`);
      console.log("");
      for (const page of pagesData.pages) {
        outputPage(page, 2);
      }
      return;
    }
  }

  // Last resort: dump raw doc info
  console.error("No content or pages found. Raw doc info:");
  console.log(JSON.stringify(docInfo, null, 2));
}

function outputPage(page: ClickUpPage, headingLevel: number): void {
  const heading = "#".repeat(Math.min(headingLevel, 6));
  console.log(`${heading} ${page.name}`);
  console.log("");

  if (page.content) {
    console.log(page.content);
    console.log("");
  }

  // Handle nested pages
  if (page.pages && page.pages.length > 0) {
    for (const subpage of page.pages) {
      outputPage(subpage, headingLevel + 1);
    }
  }
}

if (parsedDocId === "list") {
  listDocs().catch((err) => {
    console.error("Failed to list docs:", err);
    process.exit(1);
  });
} else if (pageId) {
  fetchPage(parsedDocId, pageId).catch((err) => {
    console.error("Failed to fetch page:", err);
    process.exit(1);
  });
} else {
  fetchDocPages(parsedDocId).catch((err) => {
    console.error("Failed to fetch doc:", err);
    process.exit(1);
  });
}
