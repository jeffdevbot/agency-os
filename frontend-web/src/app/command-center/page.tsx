import Link from "next/link";

export default function CommandCenterHome() {
  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">Command Center</h1>
        <p className="mt-2 text-sm text-[#4c576f]">
          Admin-only directory for clients, brands, team members, and assignments.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/command-center/clients"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Clients
          </Link>
          <Link
            href="/command-center/team"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Team
          </Link>
          <Link
            href="/command-center/tokens"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Tokens
          </Link>
          <Link
            href="/command-center/admin"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Admin
          </Link>
        </div>
      </div>
    </main>
  );
}
