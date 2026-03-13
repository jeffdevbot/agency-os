"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const formatSlugLabel = (value: string): string =>
  value
    .split("-")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const buildNavItems = (pathname: string) => {
  const segments = pathname.split("/").filter(Boolean);

  if (segments[0] === "reports" && segments[1] && segments[2] && segments[3] === "wbr") {
    const clientSlug = segments[1];
    const marketplaceCode = segments[2];

    return [
      { href: `/reports/${clientSlug}`, label: formatSlugLabel(clientSlug) },
      { href: `/reports/${clientSlug}/${marketplaceCode}/wbr/settings`, label: "Settings" },
      { href: `/reports/${clientSlug}/${marketplaceCode}/wbr/sync`, label: "Sync" },
      { href: "/", label: "Back to Tools" },
    ];
  }

  return [
    { href: "/reports", label: "Clients" },
    { href: "/", label: "Back to Tools" },
  ];
};

export default function ReportsHeader() {
  const pathname = usePathname();
  const navItems = buildNavItems(pathname);

  return (
    <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
      <div className="mx-auto flex max-w-6xl items-baseline justify-between gap-4">
        <Link href="/reports" className="flex items-baseline">
          <span className="text-2xl font-extrabold leading-none text-[#0f172a]">Reports</span>
        </Link>
        <div className="flex items-center gap-4">
          {navItems.map((item) => (
            <Link
              key={`${item.href}-${item.label}`}
              href={item.href}
              className="text-sm font-semibold text-[#0a6fd6] hover:underline"
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </header>
  );
}
