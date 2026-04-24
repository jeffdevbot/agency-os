import AppTopNav from "@/components/nav/AppTopNav";

export default function ClientsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AppTopNav />
      {children}
    </>
  );
}
