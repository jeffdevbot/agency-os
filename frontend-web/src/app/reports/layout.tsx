import { redirect } from "next/navigation";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";
import ReportsHeader from "./_components/ReportsHeader";

export default async function ReportsLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const supabase = await createSupabaseRouteClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/");
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <ReportsHeader />
      <div className="mx-auto w-full max-w-[1536px] px-5 py-6 xl:px-6 xl:py-8">{children}</div>
    </div>
  );
}
