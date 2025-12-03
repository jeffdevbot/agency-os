interface SkuData {
    sku_code: string;
    product_name: string | null;
    asin: string | null;
    brand_tone: string | null;
    target_audience: string | null;
    supplied_content: string | null;
    words_to_avoid: string[] | null;
    keywords: string[];
    questions: string[];
    customAttributes: Record<string, string>;
}

export function generateCsvTemplate(
    skus: SkuData[],
    customAttributeNames: string[]
): string {
    const headers = [
        "SKU",
        "Product Name",
        "ASIN",
        "Brand Tone",
        "Target Audience",
        "Supplied Content",
        "Words to Avoid",
        "Keywords",
        "Questions",
        ...customAttributeNames,
    ];

    const escapeField = (value: string | null | undefined): string => {
        if (!value) return "";
        const str = String(value).replace(/\n/g, " ").trim();
        if (str.includes(",") || str.includes('"') || str.includes("\n")) {
            return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
    };

    const rows = skus.map((sku) => {
        const row = [
            escapeField(sku.sku_code),
            escapeField(sku.product_name),
            escapeField(sku.asin),
            escapeField(sku.brand_tone),
            escapeField(sku.target_audience),
            escapeField(sku.supplied_content),
            escapeField((sku.words_to_avoid || []).join("|")),
            escapeField(sku.keywords.join("|")),
            escapeField(sku.questions.join("|")),
            ...customAttributeNames.map((attr) => escapeField(sku.customAttributes[attr] || "")),
        ];
        return row.join(",");
    });

    const csv = [headers.join(","), ...rows].join("\n");
    return "\uFEFF" + csv; // UTF-8 BOM for Excel
}

export function downloadCsv(filename: string, content: string) {
    const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
}
