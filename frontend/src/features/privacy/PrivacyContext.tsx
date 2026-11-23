"use client";

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useSyncExternalStore,
} from "react";
import { ConsentCategory, ConsentRecord, PrivacyContextValue } from "./types";
import {
  ORCHESTRA_CONSENT_KEY,
  isValidConsentRecord,
  saveStoredConsent,
} from "./storage";
import { canTrack as canTrackHelper } from "./telemetryGate";

const PrivacyContext = createContext<PrivacyContextValue | null>(null);

function subscribe(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  window.addEventListener("orchestra-consent-change", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("orchestra-consent-change", callback);
  };
}

function getSnapshot(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(ORCHESTRA_CONSENT_KEY);
  } catch {
    return null;
  }
}

function getServerSnapshot(): string | null {
  return null;
}

function subscribeClient(): () => void {
  return () => {};
}

function getClientSnapshot(): boolean {
  return true;
}

function getServerClientSnapshot(): boolean {
  return false;
}

export function PrivacyProvider({ children }: { children: React.ReactNode }) {
  const consentRaw = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  );

  const isHydrated = useSyncExternalStore(
    subscribeClient,
    getClientSnapshot,
    getServerClientSnapshot
  );

  const [isPreferencesOpen, setIsPreferencesOpen] = useState(false);

  const consent = useMemo<ConsentRecord | null>(() => {
    if (!consentRaw) return null;
    try {
      const parsed = JSON.parse(consentRaw);
      return isValidConsentRecord(parsed) ? parsed : null;
    } catch {
      return null;
    }
  }, [consentRaw]);

  // During SSR or pre-hydration, hasResponded defaults to true to avoid banner flash
  // Once hydrated, hasResponded is true if a valid consent record exists
  const hasResponded = !isHydrated || Boolean(consent);

  const acknowledgeEssential = useCallback(() => {
    saveStoredConsent(false);
  }, []);

  const acceptAll = useCallback(() => {
    saveStoredConsent(true);
  }, []);

  const rejectOptional = useCallback(() => {
    saveStoredConsent(false);
  }, []);

  const savePreferences = useCallback((analyticsEnabled: boolean) => {
    saveStoredConsent(analyticsEnabled);
    setIsPreferencesOpen(false);
  }, []);

  const openPreferences = useCallback(() => {
    setIsPreferencesOpen(true);
  }, []);

  const closePreferences = useCallback(() => {
    setIsPreferencesOpen(false);
  }, []);

  const canTrack = useCallback(
    (category: ConsentCategory) => {
      return canTrackHelper(category, consent);
    },
    [consent]
  );

  const contextValue = useMemo<PrivacyContextValue>(
    () => ({
      consent,
      hasResponded,
      isPreferencesOpen,
      acknowledgeEssential,
      acceptAll,
      rejectOptional,
      savePreferences,
      openPreferences,
      closePreferences,
      canTrack,
    }),
    [
      consent,
      hasResponded,
      isPreferencesOpen,
      acknowledgeEssential,
      acceptAll,
      rejectOptional,
      savePreferences,
      openPreferences,
      closePreferences,
      canTrack,
    ]
  );

  return (
    <PrivacyContext.Provider value={contextValue}>
      {children}
    </PrivacyContext.Provider>
  );
}

export function usePrivacy(): PrivacyContextValue {
  const context = useContext(PrivacyContext);
  if (!context) {
    throw new Error("usePrivacy must be used within a PrivacyProvider");
  }
  return context;
}
