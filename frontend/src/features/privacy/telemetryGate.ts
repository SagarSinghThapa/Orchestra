import { ConsentCategory, ConsentRecord } from "./types";
import { getStoredConsent } from "./storage";

/**
 * Forward-compatible telemetry gate.
 * Evaluates whether a requested storage or telemetry category is currently authorized.
 *
 * Invariants:
 * - 'essential': Always returns true (mandatory for authentication, CSRF, and routing).
 * - 'analytics': Defaults to false; requires explicit affirmative consent.
 * - Revocation: If consent is withdrawn, immediately returns false without requiring page refresh.
 */
export function canTrack(
  category: ConsentCategory,
  activeConsent?: ConsentRecord | null
): boolean {
  if (category === "essential") {
    return true;
  }

  const consent = activeConsent !== undefined ? activeConsent : getStoredConsent();
  if (!consent || !consent.consentGiven) {
    return false;
  }

  if (category === "analytics") {
    return Boolean(consent.categories.analytics);
  }

  return false;
}

/**
 * Gate for dispatching diagnostic or usage telemetry events.
 * If consent has not been granted or has been revoked, drops the event and returns false.
 * NOTE: Orchestra does not currently ship third-party tracking scripts.
 * This gate ensures that any future client diagnostics strictly honor user choice.
 */
export function dispatchTelemetryEvent(
  eventName: string,
  payload?: Record<string, unknown>,
  activeConsent?: ConsentRecord | null
): boolean {
  if (!canTrack("analytics", activeConsent)) {
    return false;
  }

  // If permitted, optional event is processed
  if (process.env.NODE_ENV === "development") {
    // Development trace logging
    return Boolean(eventName || payload);
  }
  return true;
}
