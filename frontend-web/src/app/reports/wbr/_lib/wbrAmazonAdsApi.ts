export type AmazonAdsConnection = {
  profile_id: string;
  connected_at: string | null;
  lwa_account_hint: string | null;
};

export type AmazonAdsAdvertiserProfile = {
  profileId: number;
  countryCode: string;
  currencyCode: string;
  dailyBudget: number;
  timezone: string;
  accountInfo: {
    marketplaceStringId: string;
    id: string;
    type: string;
    name: string;
  };
};

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
  }
  return url.replace(/\/+$/, "");
};

const authJsonHeaders = (token: string): Record<string, string> => ({
  Authorization: `Bearer ${token}`,
  "Content-Type": "application/json",
});

const parseErrorDetail = async (response: Response): Promise<string> => {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (typeof body?.message === "string") return body.message;
    return JSON.stringify(body);
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
};

const requestJson = async <T>(token: string, path: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(`${getBackendUrl()}${path}`, {
    ...init,
    headers: {
      ...authJsonHeaders(token),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await parseErrorDetail(response);
    throw new Error(detail);
  }

  return (await response.json()) as T;
};

type ConnectResponse = { ok: boolean; authorization_url: string };
type ConnectionStatusResponse = {
  ok: boolean;
  connected: boolean;
  connection: AmazonAdsConnection | null;
};
type ProfilesResponse = { ok: boolean; profiles: AmazonAdsAdvertiserProfile[] };

export const getAmazonAdsConnectUrl = async (
  token: string,
  profileId: string,
  returnPath: string,
): Promise<string> => {
  const data = await requestJson<ConnectResponse>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/connect`,
    {
      method: "POST",
      body: JSON.stringify({ return_path: returnPath }),
    },
  );
  return data.authorization_url;
};

export const getAmazonAdsConnectionStatus = async (
  token: string,
  profileId: string,
): Promise<{ connected: boolean; connection: AmazonAdsConnection | null }> => {
  const data = await requestJson<ConnectionStatusResponse>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/connection`,
    { method: "GET" },
  );
  return { connected: data.connected, connection: data.connection };
};

export const listAmazonAdsProfiles = async (
  token: string,
  profileId: string,
): Promise<AmazonAdsAdvertiserProfile[]> => {
  const data = await requestJson<ProfilesResponse>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/profiles`,
    { method: "GET" },
  );
  return data.profiles ?? [];
};

export const selectAmazonAdsProfile = async (
  token: string,
  profileId: string,
  amazonAdsProfileId: string,
  amazonAdsAccountId?: string,
): Promise<void> => {
  await requestJson<unknown>(
    token,
    `/admin/wbr/profiles/${profileId}/amazon-ads/select-profile`,
    {
      method: "POST",
      body: JSON.stringify({
        amazon_ads_profile_id: amazonAdsProfileId,
        amazon_ads_account_id: amazonAdsAccountId ?? null,
      }),
    },
  );
};
