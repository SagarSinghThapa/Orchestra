import { ConsentRecord } from "./types";

export const ORCHESTRA_CONSENT_KEY = "orchestra_cookie_consent_v1";

/**
 * Validates that an unparsed or parsed object conforms to ConsentRecord schema.
 */
export function isValidConsentRecord(data: unknown): data is ConsentRecord {
  if (!data || typeof data !== "object") return false;
  const record = data as Partial<ConsentRecord>;
  if (record.version !== 1) return false;
  if (typeof record.consentGiven !== "boolean") return false;
  if (!record.categories || typeof record.categories !== "object") return false;
  if (record.categories.essential !== true) return false;
  if (typeof record.categories.analytics !== "boolean") return false;
  if (typeof record.updatedAt !== "string") return false;
  return true;
}

/**
 * Safely reads the persisted consent record from localStorage.
 * Returns null if unpersisted, malformed, or if storage access is restricted.
 */
export function getStoredConsent(): ConsentRecord | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(ORCHESTRA_CONSENT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (isValidConsentRecord(parsed)) {
      return parsed;
    }
    // Invalid or legacy schema; purge cleanly
    localStorage.removeItem(ORCHESTRA_CONSENT_KEY);
    return null;
  } catch {
    // Tolerates private browsing sandbox or disabled localStorage
    return null;
  }
}

/**
 * Persists the user's consent record to localStorage.
 * Guaranteed: Only privacy category booleans and ISO timestamps are written.
 * Under no circumstances are auth tokens, credentials, or personal data stored here.
 */
export function saveStoredConsent(analyticsEnabled: boolean): ConsentRecord {
  const record: ConsentRecord = {
    version: 1,
    consentGiven: true,
    categories: {
      essential: true,
      analytics: analyticsEnabled,
    },
    updatedAt: new Date().toISOString(),
  };

  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(ORCHESTRA_CONSENT_KEY, JSON.stringify(record));
      window.dispatchEvent(new Event("orchestra-consent-change"));
    } catch {
      // Tolerate storage quota or sandbox restrictions gracefully
    }
  }

  return record;
}

/**
 * Purges stored consent from localStorage (useful for testing or full state reset).
 */
export function clearStoredConsent(): void {
  if (typeof window !== "undefined") {
    try {
      localStorage.removeItem(ORCHESTRA_CONSENT_KEY);
      window.dispatchEvent(new Event("orchestra-consent-change"));
    } catch {
      // ignore
    }
  }
}
