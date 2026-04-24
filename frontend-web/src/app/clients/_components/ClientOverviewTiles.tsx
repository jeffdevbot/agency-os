import Link from "next/link";

type ClientOverviewTilesProps = {
  clientSlug: string;
  clientId: string;
};

const tiles = (clientSlug: string, clientId: string) => [
  {
    emoji: "📈",
    title: "Reports",
    description: "Open WBR and other client reporting workflows.",
    href: `/clients/${clientSlug}/reports`,
  },
  {
    emoji: "🔌",
    title: "Data",
    description: "Manage API connections and data access for this client.",
    href: `/clients/${clientSlug}/data`,
  },
  {
    emoji: "👥",
    title: "Team",
    description: "Manage brands, team assignments, and client ownership.",
    href: `/clients/${clientSlug}/team`,
  },
];

export default function ClientOverviewTiles({
  clientSlug,
  clientId,
}: ClientOverviewTilesProps) {
  return (
    <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
      {tiles(clientSlug, clientId).map((tile) => (
        <div
          key={tile.title}
          className="flex flex-col gap-5 rounded-2xl border border-white/40 bg-white/50 p-8 text-left shadow-md backdrop-blur transition-all hover:-translate-y-0.5 hover:shadow-xl"
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl">{tile.emoji}</span>
            <div className="space-y-1">
              <p className="text-lg font-semibold text-[#0f172a]">{tile.title}</p>
              <p className="text-base leading-relaxed text-[#4c576f]">
                {tile.description}
              </p>
            </div>
          </div>
          <Link
            href={tile.href}
            className="mt-auto flex items-center justify-between rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Launch <span aria-hidden="true">→</span>
          </Link>
        </div>
      ))}
    </div>
  );
}
