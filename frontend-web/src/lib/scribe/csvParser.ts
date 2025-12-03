export async function parseCsv(file: File): Promise<Record<string, string>[]> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = (e) => {
            const text = e.target?.result as string;
            if (!text) {
                reject(new Error("Empty file"));
                return;
            }

            // Simple CSV parser (handles quoted fields)
            const lines = text.split("\n").filter((line) => line.trim());
            if (lines.length < 2) {
                reject(new Error("CSV must have headers and at least one row"));
                return;
            }

            // Auto-detect delimiter: tab or comma
            const firstLine = lines[0];
            const delimiter = firstLine.includes("\t") ? "\t" : ",";

            const headers = firstLine.split(delimiter).map((h) => h.trim().replace(/^"|"$/g, ""));
            const rows = lines.slice(1).map((line) => {
                const values: string[] = [];
                let current = "";
                let inQuotes = false;

                for (let i = 0; i < line.length; i++) {
                    const char = line[i];
                    if (char === '"') {
                        inQuotes = !inQuotes;
                    } else if (char === delimiter && !inQuotes) {
                        values.push(current.trim());
                        current = "";
                    } else {
                        current += char;
                    }
                }
                values.push(current.trim());

                const row: Record<string, string> = {};
                headers.forEach((header, i) => {
                    row[header] = (values[i] || "").replace(/^"|"$/g, "");
                });
                return row;
            });

            resolve(rows);
        };

        reader.onerror = () => reject(new Error("Failed to read file"));
        reader.readAsText(file);
    });
}
