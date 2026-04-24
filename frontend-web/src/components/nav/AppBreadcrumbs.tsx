import Link from "next/link";

type BreadcrumbItem = {
  label: string;
  href?: string;
};

type AppBreadcrumbsProps = {
  items: BreadcrumbItem[];
};

export default function AppBreadcrumbs({ items }: AppBreadcrumbsProps) {
  if (items.length === 0) {
    return null;
  }

  const lastIndex = items.length - 1;

  return (
    <nav
      aria-label="Breadcrumb"
      className="border-b border-slate-200 bg-white/80 px-6 py-3 backdrop-blur"
    >
      <ol className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 text-sm text-[#64748b]">
        {items.map((item, index) => {
          const isLast = index === lastIndex;
          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-2">
              {index > 0 ? <span aria-hidden="true">/</span> : null}
              {item.href && !isLast ? (
                <Link
                  href={item.href}
                  className="font-semibold text-[#0a6fd6] transition hover:text-[#0959ab]"
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  className={isLast ? "font-semibold text-[#0f172a]" : undefined}
                  aria-current={isLast ? "page" : undefined}
                >
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
