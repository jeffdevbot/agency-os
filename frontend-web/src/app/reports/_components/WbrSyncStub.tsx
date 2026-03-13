"use client";

import WbrSyncScreen from "./WbrSyncScreen";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function WbrSyncStub({ clientSlug, marketplaceCode }: Props) {
  return <WbrSyncScreen clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
