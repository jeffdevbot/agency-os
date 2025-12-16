import { getDelegatedAccessToken } from "@/lib/debrief/googleAuth";

export type DriveFile = {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime: string;
  webViewLink: string | null;
  owners: Array<{ displayName?: string; emailAddress?: string }> | null;
};

const DRIVE_SCOPES = [
  "https://www.googleapis.com/auth/drive.readonly",
  "https://www.googleapis.com/auth/documents.readonly",
];

const driveFetch = async (url: string | URL) => {
  const token = await getDelegatedAccessToken(DRIVE_SCOPES);
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response;
};

export const listMeetFolderFiles = async (limit: number): Promise<DriveFile[]> => {
  const folderId = process.env.GOOGLE_MEET_FOLDER_ID;
  if (!folderId) {
    throw new Error("Missing required environment variable: GOOGLE_MEET_FOLDER_ID");
  }

  const list = async (docsOnly: boolean) => {
    const parts = [
      `'${folderId}' in parents`,
      "trashed = false",
      docsOnly ? "mimeType = 'application/vnd.google-apps.document'" : null,
    ].filter(Boolean);

    const query = parts.join(" and ");
    const url = new URL("https://www.googleapis.com/drive/v3/files");
    url.searchParams.set("q", query);
    url.searchParams.set("pageSize", String(limit));
    url.searchParams.set("orderBy", "modifiedTime desc");
    url.searchParams.set(
      "fields",
      "files(id,name,mimeType,modifiedTime,webViewLink,owners(emailAddress,displayName))",
    );
    url.searchParams.set("supportsAllDrives", "true");
    url.searchParams.set("includeItemsFromAllDrives", "true");

    const response = await driveFetch(url);
    const json = (await response.json().catch(() => ({}))) as {
      files?: Array<Record<string, unknown>>;
      error?: { message?: string };
    };

    if (!response.ok) {
      throw new Error(
        `Drive API error (${response.status}): ${json.error?.message ?? JSON.stringify(json)}`,
      );
    }

    return (json.files ?? []).map((row) => ({
      id: row.id as string,
      name: row.name as string,
      mimeType: row.mimeType as string,
      modifiedTime: row.modifiedTime as string,
      webViewLink: (row.webViewLink as string | null) ?? null,
      owners: ((row.owners as Array<Record<string, unknown>> | null | undefined) ?? null)?.map(
        (owner) => ({
          displayName: owner.displayName as string | undefined,
          emailAddress: owner.emailAddress as string | undefined,
        }),
      ) ?? null,
    }));
  };

  const docs = await list(true);
  if (docs.length > 0) return docs;
  return list(false);
};

export const exportGoogleDocAsText = async (fileId: string): Promise<string> => {
  const url = new URL(`https://www.googleapis.com/drive/v3/files/${fileId}/export`);
  url.searchParams.set("mimeType", "text/plain");

  const response = await driveFetch(url);
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Drive export error (${response.status}): ${body || response.statusText}`);
  }

  return response.text();
};

