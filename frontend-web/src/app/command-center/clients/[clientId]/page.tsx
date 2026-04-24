"use client";

import { useParams } from "next/navigation";
import ClientTeamWorkspace from "@/app/clients/_components/ClientTeamWorkspace";

export default function CommandCenterClientDetailPage() {
  const params = useParams();
  const rawClientId = params.clientId;
  const clientId = Array.isArray(rawClientId) ? rawClientId[0] : rawClientId;

  return <ClientTeamWorkspace clientId={clientId ?? ""} />;
}
