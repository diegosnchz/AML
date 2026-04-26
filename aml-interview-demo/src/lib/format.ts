import type { Severity } from "@/lib/types";

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value: number, fractionDigits = 2): string {
  return new Intl.NumberFormat("es-ES", {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: 0,
  }).format(value);
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("es-ES", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function severityClasses(severity: Severity): string {
  switch (severity) {
    case "CRITICAL":
      return "bg-[#be6a6a]/18 text-[#7b2f2f] border-[#be6a6a]/35";
    case "HIGH":
      return "bg-[#c48353]/18 text-[#7b4721] border-[#c48353]/35";
    case "MEDIUM":
      return "bg-[#d5b17a]/20 text-[#6f4f22] border-[#c7a56f]/35";
    default:
      return "bg-[#86a28c]/18 text-[#2f5740] border-[#86a28c]/35";
  }
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
