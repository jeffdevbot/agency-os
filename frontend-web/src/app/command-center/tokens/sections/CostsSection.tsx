import { getOpenAICosts } from "@/app/actions/get-openai-costs";
import { CostsCard } from "../CostsCard";
import type { OpenAIDailyCost } from "@/app/actions/get-openai-costs";

export async function CostsSection(props: { rangeDays: number }) {
  const { rangeDays } = props;

  let costs: OpenAIDailyCost[] = [];
  try {
    costs = await getOpenAICosts(rangeDays);
  } catch {
    costs = [];
  }

  return <CostsCard costs={costs} rangeDays={rangeDays} />;
}
