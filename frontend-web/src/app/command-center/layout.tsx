import { redirect } from "next/navigation";
import Link from "next/link";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

export default async function CommandCenterLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/");
  }

  const { data, error } = await supabase
    .from("profiles")
    .select("is_admin")
    .eq("id", user.id)
    .single();

  if (error || !data?.is_admin) {
    redirect("/");
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-6xl items-baseline justify-between gap-4">
          <Link href="/command-center" className="flex items-baseline">
            <span className="text-2xl font-extrabold leading-none text-[#0f172a]">
              Command
            </span>
            <span className="ml-2 text-lg font-semibold leading-none text-slate-600">
              Center
            </span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/" className="text-sm font-semibold text-[#0a6fd6] hover:underline">
              Back to Tools
            </Link>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-6 py-8">{children}</div>
    </div>
  );
}
