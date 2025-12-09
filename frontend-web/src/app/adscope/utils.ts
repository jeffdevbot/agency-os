/**
 * Utility functions for AdScope
 */

export function formatCurrency(value: number, currencyCode: string): string {
  const symbol = getCurrencySymbol(currencyCode);
  return `${symbol}${value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatPercent(value: number, decimals: number = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number): string {
  return value.toLocaleString("en-US", {
    maximumFractionDigits: 0,
  });
}

export function formatCompact(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  } else if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return value.toFixed(0);
}

export function getCurrencySymbol(currencyCode: string): string {
  switch (currencyCode.toUpperCase()) {
    case "USD":
      return "$";
    case "EUR":
      return "€";
    case "GBP":
      return "£";
    default:
      return "$";
  }
}

export function getACOSColor(acos: number): string {
  if (acos < 0.15) return "text-blue-400"; // Good
  if (acos < 0.30) return "text-yellow-400"; // OK
  return "text-red-400"; // High
}

export function getACOSBgColor(acos: number): string {
  if (acos < 0.15) return "bg-blue-500/20 border-blue-500/50";
  if (acos < 0.30) return "bg-yellow-500/20 border-yellow-500/50";
  return "bg-red-500/20 border-red-500/50";
}

export function getStateBadgeColor(state: string): string {
  switch (state.toLowerCase()) {
    case "enabled":
      return "text-emerald-400 bg-emerald-500/20";
    case "paused":
      return "text-slate-400 bg-slate-500/20";
    case "archived":
      return "text-slate-500 bg-slate-600/20";
    default:
      return "text-slate-400 bg-slate-500/20";
  }
}

export function getASINThumbnailURL(asin: string): string {
  return `https://images-na.ssl-images-amazon.com/images/P/${asin}.01._THUMB_.jpg`;
}
