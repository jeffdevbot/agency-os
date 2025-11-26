import { NextResponse, type NextRequest } from "next/server";
import { createSupabaseRouteClient } from "@/lib/supabase/serverClient";

const isUuid = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);

export async function POST(
  _request: NextRequest,
  context: { params: Promise<{ projectId?: string; skuId?: string; sourceSkuId?: string }> },
) {
  const { projectId, skuId, sourceSkuId } = await context.params;

  if (!isUuid(projectId) || !isUuid(skuId) || !isUuid(sourceSkuId)) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "invalid ids" } },
      { status: 400 },
    );
  }

  if (skuId === sourceSkuId) {
    return NextResponse.json(
      { error: { code: "validation_error", message: "cannot copy SKU to itself" } },
      { status: 400 },
    );
  }

  const supabase = await createSupabaseRouteClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return NextResponse.json({ error: { code: "unauthorized", message: "Unauthorized" } }, { status: 401 });
  }

  // Verify both SKUs exist and belong to the same project
  const { data: sourceSku, error: sourceError } = await supabase
    .from("scribe_skus")
    .select("id, project_id, brand_tone, target_audience, words_to_avoid, supplied_content")
    .eq("id", sourceSkuId)
    .eq("project_id", projectId)
    .single();

  if (sourceError || !sourceSku) {
    return NextResponse.json(
      { error: { code: "not_found", message: "source SKU not found" } },
      { status: 404 },
    );
  }

  const { data: targetSku, error: targetError } = await supabase
    .from("scribe_skus")
    .select("id, project_id")
    .eq("id", skuId)
    .eq("project_id", projectId)
    .single();

  if (targetError || !targetSku) {
    return NextResponse.json(
      { error: { code: "not_found", message: "target SKU not found" } },
      { status: 404 },
    );
  }

  // Copy scalar fields from source to target
  const { error: updateError } = await supabase
    .from("scribe_skus")
    .update({
      brand_tone: sourceSku.brand_tone,
      target_audience: sourceSku.target_audience,
      words_to_avoid: sourceSku.words_to_avoid,
      supplied_content: sourceSku.supplied_content,
      updated_at: new Date().toISOString(),
    })
    .eq("id", skuId)
    .eq("project_id", projectId);

  if (updateError) {
    return NextResponse.json(
      { error: { code: "server_error", message: updateError.message } },
      { status: 500 },
    );
  }

  // Delete existing keywords for target SKU
  const { error: deleteKeywordsError } = await supabase
    .from("scribe_keywords")
    .delete()
    .eq("project_id", projectId)
    .eq("sku_id", skuId);

  if (deleteKeywordsError) {
    return NextResponse.json(
      { error: { code: "server_error", message: deleteKeywordsError.message } },
      { status: 500 },
    );
  }

  // Copy keywords from source to target
  const { data: sourceKeywords, error: keywordsError } = await supabase
    .from("scribe_keywords")
    .select("keyword, source, priority")
    .eq("project_id", projectId)
    .eq("sku_id", sourceSkuId);

  if (keywordsError) {
    return NextResponse.json(
      { error: { code: "server_error", message: keywordsError.message } },
      { status: 500 },
    );
  }

  if (sourceKeywords && sourceKeywords.length > 0) {
    const keywordsToInsert = sourceKeywords.map((kw) => ({
      project_id: projectId,
      sku_id: skuId,
      keyword: kw.keyword,
      source: kw.source,
      priority: kw.priority,
    }));

    const { error: insertKeywordsError } = await supabase
      .from("scribe_keywords")
      .insert(keywordsToInsert);

    if (insertKeywordsError) {
      return NextResponse.json(
        { error: { code: "server_error", message: insertKeywordsError.message } },
        { status: 500 },
      );
    }
  }

  // Delete existing questions for target SKU
  const { error: deleteQuestionsError } = await supabase
    .from("scribe_customer_questions")
    .delete()
    .eq("project_id", projectId)
    .eq("sku_id", skuId);

  if (deleteQuestionsError) {
    return NextResponse.json(
      { error: { code: "server_error", message: deleteQuestionsError.message } },
      { status: 500 },
    );
  }

  // Copy questions from source to target
  const { data: sourceQuestions, error: questionsError } = await supabase
    .from("scribe_customer_questions")
    .select("question, source")
    .eq("project_id", projectId)
    .eq("sku_id", sourceSkuId);

  if (questionsError) {
    return NextResponse.json(
      { error: { code: "server_error", message: questionsError.message } },
      { status: 500 },
    );
  }

  if (sourceQuestions && sourceQuestions.length > 0) {
    const questionsToInsert = sourceQuestions.map((q) => ({
      project_id: projectId,
      sku_id: skuId,
      question: q.question,
      source: q.source,
    }));

    const { error: insertQuestionsError } = await supabase
      .from("scribe_customer_questions")
      .insert(questionsToInsert);

    if (insertQuestionsError) {
      return NextResponse.json(
        { error: { code: "server_error", message: insertQuestionsError.message } },
        { status: 500 },
      );
    }
  }

  // Delete existing variant values for target SKU
  const { error: deleteVariantValuesError } = await supabase
    .from("scribe_sku_variant_values")
    .delete()
    .eq("sku_id", skuId);

  if (deleteVariantValuesError) {
    return NextResponse.json(
      { error: { code: "server_error", message: deleteVariantValuesError.message } },
      { status: 500 },
    );
  }

  // Copy variant values from source to target
  const { data: sourceVariantValues, error: variantValuesError } = await supabase
    .from("scribe_sku_variant_values")
    .select("attribute_id, value")
    .eq("sku_id", sourceSkuId);

  if (variantValuesError) {
    return NextResponse.json(
      { error: { code: "server_error", message: variantValuesError.message } },
      { status: 500 },
    );
  }

  if (sourceVariantValues && sourceVariantValues.length > 0) {
    const variantValuesToInsert = sourceVariantValues.map((vv) => ({
      sku_id: skuId,
      attribute_id: vv.attribute_id,
      value: vv.value,
    }));

    const { error: insertVariantValuesError } = await supabase
      .from("scribe_sku_variant_values")
      .insert(variantValuesToInsert);

    if (insertVariantValuesError) {
      return NextResponse.json(
        { error: { code: "server_error", message: insertVariantValuesError.message } },
        { status: 500 },
      );
    }
  }

  return NextResponse.json({ ok: true });
}
