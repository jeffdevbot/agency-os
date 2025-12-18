import { getInternalUsage } from "@/app/actions/get-internal-usage";
import { InternalAttributionCard } from "../InternalAttributionCard";

export async function InternalSection(props: { rangeDays: number }) {
  const { rangeDays } = props;
  const internal = await getInternalUsage(rangeDays);
  return <InternalAttributionCard internal={internal} />;
}
