import fs from "node:fs/promises";
import { JWT } from "google-auth-library";

type ServiceAccountKey = {
  client_email?: string;
  private_key?: string;
};

const readServiceAccountKey = async (): Promise<ServiceAccountKey> => {
  const raw = process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (!raw) {
    throw new Error("Missing required environment variable: GOOGLE_SERVICE_ACCOUNT_JSON");
  }

  if (raw.trim().startsWith("{")) {
    return JSON.parse(raw) as ServiceAccountKey;
  }

  const contents = await fs.readFile(raw, "utf8");
  return JSON.parse(contents) as ServiceAccountKey;
};

export const getDelegatedAccessToken = async (scopes: string[]): Promise<string> => {
  const impersonationEmail = process.env.GOOGLE_IMPERSONATION_EMAIL;
  if (!impersonationEmail) {
    throw new Error("Missing required environment variable: GOOGLE_IMPERSONATION_EMAIL");
  }

  const key = await readServiceAccountKey();
  if (!key.client_email || !key.private_key) {
    throw new Error("Invalid GOOGLE_SERVICE_ACCOUNT_JSON: missing client_email/private_key");
  }

  const auth = new JWT({
    email: key.client_email,
    key: key.private_key,
    subject: impersonationEmail,
    scopes,
  });

  const { token } = await auth.getAccessToken();
  if (!token) {
    throw new Error("Failed to obtain Google access token");
  }

  return token;
};

