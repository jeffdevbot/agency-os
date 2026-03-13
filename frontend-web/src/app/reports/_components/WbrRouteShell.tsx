"use client";

import WbrSection1ReportScreen from "./WbrSection1ReportScreen";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function WbrRouteShell({ clientSlug, marketplaceCode }: Props) {
  return <WbrSection1ReportScreen clientSlug={clientSlug} marketplaceCode={marketplaceCode} />;
}
