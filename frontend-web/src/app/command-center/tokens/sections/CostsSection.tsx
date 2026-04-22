import { getOpenAICosts } from "@/app/actions/get-openai-costs";
import { CostsCard } from "../CostsCard";
import type { OpenAICostsResult } from "@/app/actions/get-openai-costs";

export async function CostsSection(props: { rangeDays: number }) {
  const { rangeDays } = props;

  let result: OpenAICostsResult;
  try {
    result = await getOpenAICosts(rangeDays);
  } catch (error) {
    result = {
      status: "fetch_error",
      costs: [],
      message: error instanceof Error ? error.message : "Official spend is currently unavailable.",
    };
  }

  return <CostsCard costs={result.costs} rangeDays={rangeDays} status={result.status} message={result.message} />;
}
