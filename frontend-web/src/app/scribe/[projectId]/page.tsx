"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ScribeHeader } from "../components/ScribeHeader";
import { ScribeProgressTracker } from "../components/ScribeProgressTracker";
import { CustomAttributesInput } from "./components/CustomAttributesInput";
import { SkuCard } from "./components/SkuCard";
import { EditSkuPanel } from "./components/EditSkuPanel";
import { generateCsvTemplate, downloadCsv } from "@/lib/scribe/csvHelpers";
import { parseCsv } from "@/lib/scribe/csvParser";

interface Project {
    id: string;
    name: string;
    custom_attributes: string[] | null;
}

interface Sku {
    id: string;
    skuCode: string;
    productName: string | null;
    asin: string | null;
    brandTone: string | null;
    targetAudience: string | null;
    suppliedContent: string | null;
    wordsToAvoid: string[] | null;
    updatedAt: string;
}

export default function StageAPage() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.projectId as string;

    const [project, setProject] = useState<Project | null>(null);
    const [skus, setSkus] = useState<Sku[]>([]);
    const [variantAttributes, setVariantAttributes] = useState<any[]>([]);
    const [keywordCounts, setKeywordCounts] = useState<Record<string, number>>({});
    const [questionCounts, setQuestionCounts] = useState<Record<string, number>>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [editingSkuId, setEditingSkuId] = useState<string | null>(null);
    const [editingKeywords, setEditingKeywords] = useState<string[]>([]);
    const [editingQuestions, setEditingQuestions] = useState<string[]>([]);
    const [editingAttributeValues, setEditingAttributeValues] = useState<Record<string, string>>({});

    const customAttributes = variantAttributes.map((attr) => attr.name);

    useEffect(() => {
        loadData();
    }, [projectId]);

    useEffect(() => {
        if (editingSkuId && editingSkuId !== "new") {
            // Fetch keywords and questions for the editing SKU
            Promise.all([
                fetch(`/api/scribe/projects/${projectId}/keywords`).then(r => r.json()),
                fetch(`/api/scribe/projects/${projectId}/questions`).then(r => r.json()),
            ]).then(([allKeywords, allQuestions]) => {
                const skuKeywords = allKeywords.filter((kw: any) => kw.skuId === editingSkuId).map((kw: any) => kw.keyword);
                const skuQuestions = allQuestions.filter((q: any) => q.skuId === editingSkuId).map((q: any) => q.question);
                setEditingKeywords(skuKeywords);
                setEditingQuestions(skuQuestions);
            });

            // Fetch custom attribute values
            const fetchAttrValues = async () => {
                const valuesMap: Record<string, string> = {};

                await Promise.all(variantAttributes.map(async (attr) => {
                    try {
                        const res = await fetch(`/api/scribe/projects/${projectId}/variant-attributes/${attr.id}/values`);
                        if (res.ok) {
                            const values = await res.json();
                            // values is array of { skuId, value, ... }
                            const match = values.find((v: any) => v.skuId === editingSkuId);
                            if (match) {
                                valuesMap[attr.name] = match.value;
                            }
                        }
                    } catch (e) {
                        console.error(`Error fetching values for ${attr.name}:`, e);
                    }
                }));

                setEditingAttributeValues(valuesMap);
            };

            fetchAttrValues();
        } else {
            setEditingKeywords([]);
            setEditingQuestions([]);
            setEditingAttributeValues({});
        }
    }, [editingSkuId, projectId, variantAttributes]);

    const loadData = async () => {
        setLoading(true);
        setError(null);

        try {
            // Fetch project
            const projectRes = await fetch(`/api/scribe/projects/${projectId}`);
            if (!projectRes.ok) throw new Error("Failed to load project");
            const projectData = await projectRes.json();
            setProject(projectData);

            // Fetch SKUs
            const skusRes = await fetch(`/api/scribe/projects/${projectId}/skus`);
            if (!skusRes.ok) throw new Error("Failed to load SKUs");
            const skusData = await skusRes.json();
            setSkus(skusData);

            // Fetch variant attributes
            const attrsRes = await fetch(`/api/scribe/projects/${projectId}/variant-attributes`);
            if (attrsRes.ok) {
                const attrsData = await attrsRes.json();
                setVariantAttributes(attrsData);
            }

            // Fetch keywords and questions for counts
            const keywordsRes = await fetch(`/api/scribe/projects/${projectId}/keywords`);
            const questionsRes = await fetch(`/api/scribe/projects/${projectId}/questions`);

            if (keywordsRes.ok) {
                const keywordsData = await keywordsRes.json();
                const counts: Record<string, number> = {};
                keywordsData.forEach((kw: any) => {
                    counts[kw.skuId] = (counts[kw.skuId] || 0) + 1;
                });
                setKeywordCounts(counts);
            }

            if (questionsRes.ok) {
                const questionsData = await questionsRes.json();
                const counts: Record<string, number> = {};
                questionsData.forEach((q: any) => {
                    counts[q.skuId] = (counts[q.skuId] || 0) + 1;
                });
                setQuestionCounts(counts);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load data");
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadCsv = async () => {
        try {
            // Fetch all keywords and questions
            const [keywordsRes, questionsRes] = await Promise.all([
                fetch(`/api/scribe/projects/${projectId}/keywords`),
                fetch(`/api/scribe/projects/${projectId}/questions`),
            ]);

            const keywordsData = keywordsRes.ok ? await keywordsRes.json() : [];
            const questionsData = questionsRes.ok ? await questionsRes.json() : [];

            const keywordMap: Record<string, string[]> = {};
            keywordsData.forEach((kw: any) => {
                const skuId = kw.skuId || kw.sku_id;
                if (!skuId) return;
                keywordMap[skuId] = keywordMap[skuId] || [];
                if (kw.keyword) keywordMap[skuId].push(kw.keyword);
            });

            const questionMap: Record<string, string[]> = {};
            questionsData.forEach((q: any) => {
                const skuId = q.skuId || q.sku_id;
                if (!skuId) return;
                questionMap[skuId] = questionMap[skuId] || [];
                if (q.question) questionMap[skuId].push(q.question);
            });

            // Fetch custom attribute values per attribute
            const attrValueMap: Record<string, Record<string, string>> = {};
            await Promise.all(
                variantAttributes.map(async (attr) => {
                    try {
                        const res = await fetch(`/api/scribe/projects/${projectId}/variant-attributes/${attr.id}/values`);
                        if (!res.ok) return;
                        const values = await res.json();
                        values.forEach((v: any) => {
                            const skuId = v.skuId || v.sku_id;
                            if (!skuId) return;
                            attrValueMap[skuId] = attrValueMap[skuId] || {};
                            attrValueMap[skuId][attr.name] = v.value || "";
                        });
                    } catch (err) {
                        console.error(`Error fetching values for ${attr.name}:`, err);
                    }
                })
            );

            const skuData = skus.map((sku) => ({
                sku_code: sku.skuCode,
                product_name: sku.productName,
                asin: sku.asin,
                brand_tone: sku.brandTone,
                target_audience: sku.targetAudience,
                supplied_content: sku.suppliedContent,
                words_to_avoid: sku.wordsToAvoid,
                keywords: keywordMap[sku.id] || [],
                questions: questionMap[sku.id] || [],
                customAttributes: attrValueMap[sku.id] || {},
            }));

            const csv = generateCsvTemplate(skuData, customAttributes);
            downloadCsv(`${project?.name || "scribe"}_skus.csv`, csv);
        } catch (err) {
            console.error("Download CSV failed:", err);
            alert(err instanceof Error ? err.message : "Failed to download CSV");
        }
    };

    const handleUploadCsv = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        try {
            const rows = await parseCsv(file);
            console.log("Parsed CSV rows:", rows);

            if (rows.length === 0) return;

            // Identify custom attributes from headers
            const standardHeaders = new Set([
                "SKU", "Product Name", "ASIN", "Brand Tone", "Target Audience",
                "Supplied Content", "Words to Avoid", "Keywords", "Questions"
            ]);

            const headers = Object.keys(rows[0]);
            const customHeaders = headers.filter(h => !standardHeaders.has(h));

            // Map of attribute name -> ID
            const attrMap = new Map<string, string>();
            variantAttributes.forEach(attr => attrMap.set(attr.name, attr.id));

            // Create missing attributes
            for (const header of customHeaders) {
                if (!attrMap.has(header)) {
                    console.log(`Creating new attribute: ${header}`);
                    try {
                        const res = await fetch(`/api/scribe/projects/${projectId}/variant-attributes`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ name: header }),
                        });

                        if (res.ok) {
                            const newAttr = await res.json();
                            attrMap.set(header, newAttr.id);
                            console.log(`Created attribute ${header} with ID ${newAttr.id}`);
                        } else {
                            console.error(`Failed to create attribute ${header}:`, await res.text());
                        }
                    } catch (err) {
                        console.error(`Error creating attribute ${header}:`, err);
                    }
                }
            }

            // Upsert each row
            for (const row of rows) {
                const skuCode = row["SKU"]?.trim();
                if (!skuCode) continue;

                console.log("Processing row:", row);

                const existingSku = skus.find((s) => s.skuCode === skuCode);
                const payload = {
                    sku_code: skuCode,
                    product_name: row["Product Name"] || null,
                    asin: row["ASIN"] || null,
                    brand_tone: row["Brand Tone"] || null,
                    target_audience: row["Target Audience"] || null,
                    supplied_content: row["Supplied Content"] || null,
                    words_to_avoid: row["Words to Avoid"]?.split("|").filter(Boolean) || [],
                };

                console.log("Payload:", payload);

                const url = existingSku
                    ? `/api/scribe/projects/${projectId}/skus/${existingSku.id}`
                    : `/api/scribe/projects/${projectId}/skus`;
                const method = existingSku ? "PATCH" : "POST";

                const res = await fetch(url, {
                    method,
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });

                console.log("API Response status:", res.status);

                if (!res.ok) {
                    const errorText = await res.text();
                    console.error("Failed to save SKU:", errorText);
                    alert(`Failed to save SKU ${skuCode}: ${errorText}`);
                    continue;
                }

                const savedSku = await res.json();
                console.log("Saved SKU:", savedSku);
                const skuId = savedSku.id || existingSku?.id;

                if (!skuId) {
                    console.error("No SKU ID found for row", row);
                    continue;
                }

                // Delete existing keywords first (for clean re-upload)
                try {
                    const existingKwRes = await fetch(`/api/scribe/projects/${projectId}/keywords?skuId=${skuId}`);
                    if (existingKwRes.ok) {
                        const existingKeywords = await existingKwRes.json();
                        for (const kw of existingKeywords) {
                            await fetch(`/api/scribe/projects/${projectId}/keywords?id=${kw.id}`, { method: "DELETE" });
                        }
                    }
                } catch (err) {
                    console.error("Error deleting existing keywords:", err);
                }

                // Save keywords
                const keywords = row["Keywords"]?.split("|").filter(Boolean) || [];
                if (keywords.length > 0) {
                    console.log(`Saving ${keywords.length} keywords for SKU ${skuCode}`);
                    for (const keyword of keywords) {
                        try {
                            const kwRes = await fetch(`/api/scribe/projects/${projectId}/keywords`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ skuId, keyword: keyword.trim() }),
                            });
                            if (!kwRes.ok) console.error(`Failed to save keyword "${keyword}":`, await kwRes.text());
                        } catch (err) {
                            console.error(`Error saving keyword "${keyword}":`, err);
                        }
                    }
                }

                // Delete existing questions first (for clean re-upload)
                try {
                    const existingQRes = await fetch(`/api/scribe/projects/${projectId}/questions?skuId=${skuId}`);
                    if (existingQRes.ok) {
                        const existingQuestions = await existingQRes.json();
                        for (const q of existingQuestions) {
                            await fetch(`/api/scribe/projects/${projectId}/questions?id=${q.id}`, { method: "DELETE" });
                        }
                    }
                } catch (err) {
                    console.error("Error deleting existing questions:", err);
                }

                // Save questions
                const questions = row["Questions"]?.split("|").filter(Boolean) || [];
                if (questions.length > 0) {
                    console.log(`Saving ${questions.length} questions for SKU ${skuCode}`);
                    for (const question of questions) {
                        try {
                            const qRes = await fetch(`/api/scribe/projects/${projectId}/questions`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ skuId, question: question.trim() }),
                            });
                            if (!qRes.ok) console.error(`Failed to save question "${question}":`, await qRes.text());
                        } catch (err) {
                            console.error(`Error saving question "${question}":`, err);
                        }
                    }
                }

                // Save custom attribute values
                for (const header of customHeaders) {
                    const attrId = attrMap.get(header);
                    const value = row[header];

                    if (attrId && value) {
                        console.log(`Saving value "${value}" for attribute ${header} (ID: ${attrId})`);
                        try {
                            const valRes = await fetch(`/api/scribe/projects/${projectId}/variant-attributes/${attrId}/values`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ skuId, value: value.trim() }),
                            });
                            if (!valRes.ok) console.error(`Failed to save value for ${header}:`, await valRes.text());
                        } catch (err) {
                            console.error(`Error saving value for ${header}:`, err);
                        }
                    }
                }
            }

            // Reload data
            loadData();
            alert(`Uploaded ${rows.length} SKUs successfully`);
        } catch (err) {
            console.error("CSV upload error:", err);
            alert(err instanceof Error ? err.message : "Failed to upload CSV");
        }

        // Reset file input
        e.target.value = "";
    };

    const handleDeleteSku = async (skuId: string) => {
        if (!confirm("Are you sure you want to delete this SKU?")) return;

        try {
            const res = await fetch(`/api/scribe/projects/${projectId}/skus/${skuId}`, {
                method: "DELETE",
            });
            if (!res.ok) throw new Error("Failed to delete SKU");

            setSkus(skus.filter((s) => s.id !== skuId));
        } catch (err) {
            alert(err instanceof Error ? err.message : "Failed to delete SKU");
        }
    };

    const editingSku = editingSkuId ? skus.find((s) => s.id === editingSkuId) : null;

    if (loading) {
        return (
            <div className="flex min-h-screen flex-col bg-slate-50">
                <ScribeHeader />
                <div className="flex flex-1 items-center justify-center">
                    <p className="text-slate-600">Loading...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex min-h-screen flex-col bg-slate-50">
                <ScribeHeader />
                <div className="flex flex-1 items-center justify-center">
                    <p className="text-red-600">{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen flex-col bg-slate-50">
            <ScribeHeader />
            <ScribeProgressTracker
                currentStage="A"
                stageAComplete={skus.length > 0}
                stageBComplete={false}
                stageCComplete={false}
                onNavigate={(stage) => {
                    if (stage === "B") router.push(`/scribe/${projectId}/stage-b`);
                    if (stage === "C") router.push(`/scribe/${projectId}/stage-c`);
                }}
            />

            <div className="mx-auto w-full max-w-6xl px-6 py-8">
                {/* Custom Attributes */}
                <CustomAttributesInput
                    projectId={projectId}
                    initialAttributes={customAttributes}
                    onSave={(attrs) => loadData()}
                />

                {/* Actions */}
                <div className="mt-6 flex items-center gap-3">
                    <button
                        onClick={handleDownloadCsv}
                        className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                        Download CSV Template
                    </button>
                    <label className="cursor-pointer rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                        Upload CSV
                        <input
                            type="file"
                            accept=".csv"
                            className="hidden"
                            onChange={handleUploadCsv}
                        />
                    </label>
                    <button
                        onClick={() => setEditingSkuId("new")}
                        className="ml-auto rounded-lg bg-[#0a6fd6] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#0959ab]"
                    >
                        + Add SKU
                    </button>
                </div>

                {/* SKU List */}
                <div className="mt-6">
                    {skus.length === 0 ? (
                        <div className="rounded-lg border border-slate-200 bg-white p-12 text-center shadow-sm">
                            <h3 className="text-lg font-medium text-slate-900">No SKUs yet</h3>
                            <p className="mt-1 text-sm text-slate-600">
                                Add your first SKU to begin.
                            </p>
                            <button
                                onClick={() => setEditingSkuId("new")}
                                className="mt-4 rounded-lg bg-[#0a6fd6] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#0959ab]"
                            >
                                + Add SKU
                            </button>
                        </div>
                    ) : (
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            {skus.map((sku) => (
                                <SkuCard
                                    key={sku.id}
                                    sku={sku}
                                    keywordCount={keywordCounts[sku.id] || 0}
                                    questionCount={questionCounts[sku.id] || 0}
                                    onEdit={() => setEditingSkuId(sku.id)}
                                    onDelete={() => handleDeleteSku(sku.id)}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Edit Panel */}
            {editingSkuId && (
                <EditSkuPanel
                    projectId={projectId}
                    sku={editingSkuId === "new" ? null : editingSku || null}
                    customAttributes={customAttributes}
                    customAttributeValues={editingAttributeValues}
                    keywords={editingKeywords}
                    questions={editingQuestions}
                    onClose={() => setEditingSkuId(null)}
                    onSave={() => {
                        loadData();
                        setEditingSkuId(null);
                    }}
                />
            )}
        </div>
    );
}
