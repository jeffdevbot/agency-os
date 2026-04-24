import Link from "next/link";

export default function AppTopNav() {
  return (
    <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
      <div className="mx-auto flex max-w-6xl items-baseline gap-4">
        <Link href="/" className="flex items-baseline" aria-label="Ecomlabs Tools home">
          <span className="text-2xl font-extrabold leading-none text-[#0f172a]">
            Ecom
          </span>
          <span className="text-2xl font-extrabold leading-none text-[#0a6fd6]">
            labs
          </span>
          <span className="ml-2 text-lg font-semibold leading-none text-slate-600">
            Tools
          </span>
        </Link>
      </div>
    </header>
  );
}
