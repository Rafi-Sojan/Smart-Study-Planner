import type { FeatureKind, FeatureValue } from "./types";

export function humanizeFeatureName(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function coerceFeatureValue(raw: string, kind: FeatureKind): FeatureValue {
  const value = raw.trim();
  if (!value) return null;
  if (kind === "boolean") {
    if (["true", "1", "yes"].includes(value.toLowerCase())) return true;
    if (["false", "0", "no"].includes(value.toLowerCase())) return false;
    throw new Error("Enter true or false");
  }
  if (kind === "number") {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) throw new Error("Enter a finite number");
    return numberValue;
  }
  if (kind === "unknown" && /^[-+]?\d+(\.\d+)?$/.test(value)) {
    return Number(value);
  }
  return value;
}

export function localDateTime(hoursFromNow: number): string {
  const date = new Date(Date.now() + hoursFromNow * 60 * 60 * 1000);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function toIsoDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) throw new Error("Enter a valid date and time");
  return parsed.toISOString();
}

export function riskBand(score: number, threshold: number): string {
  if (score >= threshold) return "Support review suggested";
  if (score >= threshold * 0.75) return "Watch and review";
  return "No alert at this threshold";
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
