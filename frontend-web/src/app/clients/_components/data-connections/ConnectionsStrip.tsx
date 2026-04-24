"use client";

import type { SpApiRegionCode } from "@/app/reports/_lib/reportApiAccessApi";
import ProviderConnectionCard, {
  type ProviderConnectionState,
  type ProviderKind,
} from "./ProviderConnectionCard";

export type ConnectionCardModel = {
  state: ProviderConnectionState;
  accountId?: string | null;
  lastValidatedAt?: Date | null;
  errorMessage?: string | null;
  additionalAccountCount?: number;
};

type Props = {
  region: SpApiRegionCode;
  adsConnection: ConnectionCardModel;
  spApiConnection: ConnectionCardModel;
  pendingAction?: string | null;
  onConnect(provider: ProviderKind): void;
  onValidate(provider: ProviderKind): void;
  onDisconnect(provider: ProviderKind): void;
};

export default function ConnectionsStrip({
  region,
  adsConnection,
  spApiConnection,
  pendingAction,
  onConnect,
  onValidate,
  onDisconnect,
}: Props) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ProviderConnectionCard
        provider="amazon-ads"
        region={region}
        {...adsConnection}
        actionPending={pendingAction === `${region}:amazon-ads`}
        onConnect={() => onConnect("amazon-ads")}
        onValidate={() => onValidate("amazon-ads")}
        onDisconnect={() => onDisconnect("amazon-ads")}
      />
      <ProviderConnectionCard
        provider="sp-api"
        region={region}
        {...spApiConnection}
        actionPending={pendingAction === `${region}:sp-api`}
        onConnect={() => onConnect("sp-api")}
        onValidate={() => onValidate("sp-api")}
        onDisconnect={() => onDisconnect("sp-api")}
      />
    </div>
  );
}
