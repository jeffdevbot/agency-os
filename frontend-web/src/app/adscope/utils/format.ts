export const formatCurrency = (value: number, currency: string = "USD"): string => {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value);
};

export const formatPercent = (value: number): string => {
    return new Intl.NumberFormat("en-US", {
        style: "percent",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value);
};

export const formatNumber = (value: number): string => {
    return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    }).format(value);
};

export const formatCompact = (value: number): string => {
    return new Intl.NumberFormat("en-US", {
        notation: "compact",
        compactDisplay: "short",
        maximumFractionDigits: 1,
    }).format(value);
};
