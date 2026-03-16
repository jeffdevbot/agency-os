export type ReportsHeaderLink = {
  href: string;
  label: string;
  active?: boolean;
};

export type ReportsHeaderState = {
  title: string;
  subtitle: string;
  surfaceLinks: ReportsHeaderLink[];
  actionLinks: ReportsHeaderLink[];
};

const formatSlugLabel = (value: string): string =>
  value
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const formatMarketplaceLabel = (value: string): string => value.toUpperCase();

export function buildReportsHeaderState(pathname: string): ReportsHeaderState {
  const segments = pathname.split("/").filter(Boolean);

  if (
    segments[0] === "reports" &&
    segments[1] &&
    segments[2] &&
    (segments[3] === "wbr" || segments[3] === "pnl")
  ) {
    const clientSlug = segments[1];
    const marketplaceCode = segments[2];
    const surface = segments[3];
    const basePath = `/reports/${clientSlug}/${marketplaceCode}`;
    const isWbr = surface === "wbr";
    const isWbrSettings = isWbr && segments[4] === "settings";
    const isWbrSync = isWbr && segments[4] === "sync";

    return {
      title: "Reports",
      subtitle: `${formatSlugLabel(clientSlug)} / ${formatMarketplaceLabel(marketplaceCode)}`,
      surfaceLinks: [
        { href: `${basePath}/wbr`, label: "WBR", active: isWbr },
        { href: `${basePath}/pnl`, label: "Monthly P&L", active: surface === "pnl" },
      ],
      actionLinks: [
        ...(isWbr
          ? [
              { href: `${basePath}/wbr`, label: "Report", active: !isWbrSettings && !isWbrSync },
              { href: `${basePath}/wbr/settings`, label: "Settings", active: isWbrSettings },
              { href: `${basePath}/wbr/sync`, label: "Sync", active: isWbrSync },
            ]
          : []),
        { href: `/reports/${clientSlug}`, label: "Client Hub" },
        { href: "/", label: "Back to Tools" },
      ],
    };
  }

  if (segments[0] === "reports" && segments[1]) {
    return {
      title: "Reports",
      subtitle: formatSlugLabel(segments[1]),
      surfaceLinks: [],
      actionLinks: [
        { href: "/reports", label: "Clients" },
        { href: "/", label: "Back to Tools" },
      ],
    };
  }

  return {
    title: "Reports",
    subtitle: "Client-first reporting for WBR and Monthly P&L.",
    surfaceLinks: [],
    actionLinks: [
      { href: "/reports", label: "Clients", active: segments[0] === "reports" },
      { href: "/", label: "Back to Tools" },
    ],
  };
}
