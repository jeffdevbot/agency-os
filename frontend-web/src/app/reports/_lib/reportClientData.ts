import { listWbrProfiles, type WbrProfile } from "../wbr/_lib/wbrApi";

export type Client = {
  id: string;
  name: string;
  status: string;
};

export type ClientsResponse = {
  clients?: Client[];
  error?: {
    message?: string;
  };
};

export type ClientProfileSummary = {
  client: Client;
  profiles: WbrProfile[];
};

export const slugifyClientName = (value: string): string =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

export const loadActiveClients = async (): Promise<Client[]> => {
  const response = await fetch("/api/command-center/clients", { cache: "no-store" });
  const json = (await response.json()) as ClientsResponse;
  if (!response.ok) {
    throw new Error(json.error?.message ?? "Unable to load clients");
  }
  return (json.clients ?? []).filter((client) => client.status !== "archived");
};

export const findClientBySlug = (clients: Client[], clientSlug: string): Client | null =>
  clients.find((client) => slugifyClientName(client.name) === clientSlug) ?? null;

export const findClientById = (clients: Client[], clientId: string): Client | null =>
  clients.find((client) => client.id === clientId) ?? null;

export const loadClientProfileSummaries = async (
  token: string
): Promise<{
  summaries: ClientProfileSummary[];
  failures: string[];
}> => {
  const clients = await loadActiveClients();
  const profileResults = await Promise.allSettled(
    clients.map(async (client) => ({
      client,
      profiles: await listWbrProfiles(token, client.id),
    }))
  );

  const summaries: ClientProfileSummary[] = [];
  const failures: string[] = [];

  profileResults.forEach((result, index) => {
    const client = clients[index];
    if (!client) return;

    if (result.status === "fulfilled") {
      summaries.push(result.value);
      return;
    }

    const reason = result.reason instanceof Error ? result.reason.message : String(result.reason);
    failures.push(`${client.name}: ${reason}`);
  });

  return { summaries, failures };
};

export const findClientSummaryBySlug = (
  summaries: ClientProfileSummary[],
  clientSlug: string
): ClientProfileSummary | null =>
  summaries.find((summary) => slugifyClientName(summary.client.name) === clientSlug) ?? null;

export const loadClientProfileSummaryBySlug = async (
  token: string,
  clientSlug: string
): Promise<ClientProfileSummary> => {
  const clients = await loadActiveClients();
  const client = findClientBySlug(clients, clientSlug);

  if (!client) {
    throw new Error("Client report hub not found.");
  }

  return {
    client,
    profiles: await listWbrProfiles(token, client.id),
  };
};
