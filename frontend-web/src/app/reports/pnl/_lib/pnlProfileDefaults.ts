export function defaultPnlCurrencyCode(marketplaceCode: string): string {
  return marketplaceCode.trim().toUpperCase() === "CA" ? "CAD" : "USD";
}
