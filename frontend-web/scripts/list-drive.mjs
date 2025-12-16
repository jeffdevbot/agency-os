import fs from "node:fs/promises";
import process from "node:process";
import { JWT } from "google-auth-library";

const loadDotEnvFile = async (path) => {
  try {
    const contents = await fs.readFile(path, "utf8");
    for (const rawLine of contents.split("\n")) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const idx = line.indexOf("=");
      if (idx === -1) continue;
      const key = line.slice(0, idx).trim();
      if (!key) continue;
      if (process.env[key] !== undefined) continue;
      let value = line.slice(idx + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      process.env[key] = value;
    }
  } catch {
    // ignore missing env file
  }
};

const readServiceAccountJson = async () => {
  const raw = process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (!raw) {
    throw new Error("Missing env var GOOGLE_SERVICE_ACCOUNT_JSON");
  }

  if (raw.trim().startsWith("{")) {
    return JSON.parse(raw);
  }

  const contents = await fs.readFile(raw, "utf8");
  return JSON.parse(contents);
};

const main = async () => {
  await loadDotEnvFile(new URL("../.env.local", import.meta.url));
  await loadDotEnvFile(new URL("../.env", import.meta.url));

  const folderId = process.env.GOOGLE_MEET_FOLDER_ID;
  const subject = process.env.GOOGLE_IMPERSONATION_EMAIL;
  const maxResults = Number.parseInt(process.env.DEBRIEF_DRIVE_LIMIT ?? "10", 10);

  if (!folderId) throw new Error("Missing env var GOOGLE_MEET_FOLDER_ID");
  if (!subject) throw new Error("Missing env var GOOGLE_IMPERSONATION_EMAIL");

  const serviceAccount = await readServiceAccountJson();
  const clientEmail = serviceAccount.client_email;
  const privateKey = serviceAccount.private_key;

  if (!clientEmail || !privateKey) {
    throw new Error("Invalid service account JSON: missing client_email/private_key");
  }

  const auth = new JWT({
    email: clientEmail,
    key: privateKey,
    subject,
    scopes: [
      "https://www.googleapis.com/auth/drive.readonly",
      "https://www.googleapis.com/auth/documents.readonly",
    ],
  });

  const { token } = await auth.getAccessToken();
  if (!token) throw new Error("Failed to obtain Google access token");

  const listFiles = async (docsOnly) => {
    const parts = [
      `'${folderId}' in parents`,
      "trashed = false",
      docsOnly ? "mimeType = 'application/vnd.google-apps.document'" : null,
    ].filter(Boolean);

    const query = parts.join(" and ");
    const url = new URL("https://www.googleapis.com/drive/v3/files");
    url.searchParams.set("q", query);
    url.searchParams.set("pageSize", String(maxResults));
    url.searchParams.set("orderBy", "modifiedTime desc");
    url.searchParams.set("fields", "files(id,name,mimeType,modifiedTime,webViewLink,owners(emailAddress,displayName))");
    url.searchParams.set("supportsAllDrives", "true");
    url.searchParams.set("includeItemsFromAllDrives", "true");

    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const json = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(`Drive API error (${response.status}): ${JSON.stringify(json)}`);
    }

    return json.files ?? [];
  };

  const docs = await listFiles(true);
  const files = docs.length > 0 ? docs : await listFiles(false);

  console.log(
    JSON.stringify(
      {
        impersonating: subject,
        folderId,
        docsOnly: docs.length > 0,
        count: files.length,
        files,
      },
      null,
      2,
    ),
  );
};

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
