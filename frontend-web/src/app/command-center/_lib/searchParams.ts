export type SearchParamsRecord = Record<string, string | string[] | undefined>;

export type SearchParamsSource =
  | SearchParamsRecord
  | Promise<SearchParamsRecord | undefined>
  | undefined;

export const resolveSearchParams = async (
  source: SearchParamsSource,
): Promise<SearchParamsRecord | undefined> => {
  if (!source) return undefined;
  return await source;
};

export const getSearchParam = (
  params: SearchParamsRecord | undefined,
  key: string,
): string | undefined => {
  const raw = params?.[key];
  if (!raw) return undefined;
  return Array.isArray(raw) ? raw[0] : raw;
};

export const parseAllowedRange = (
  value: unknown,
  allowed: readonly number[],
  fallback: number,
): number => {
  const parsed = typeof value === "string" ? Number(value) : NaN;
  if (!Number.isFinite(parsed)) return fallback;
  return allowed.includes(parsed) ? parsed : fallback;
};
