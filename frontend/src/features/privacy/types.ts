export type ConsentCategory = "essential" | "analytics";

export interface ConsentCategories {
  /** Strictly necessary cookies and storage; mandatory for basic operation */
  essential: true;
  /** Optional telemetry / diagnostics; defaults to false, inactive in current release */
  analytics: boolean;
}

export interface ConsentRecord {
  version: 1;
  consentGiven: boolean;
  categories: ConsentCategories;
  updatedAt: string; // ISO 8601 timestamp
}

export interface PrivacyContextValue {
  consent: ConsentRecord | null;
  hasResponded: boolean;
  isPreferencesOpen: boolean;
  acknowledgeEssential: () => void;
  acceptAll: () => void;
  rejectOptional: () => void;
  savePreferences: (analyticsEnabled: boolean) => void;
  openPreferences: () => void;
  closePreferences: () => void;
  canTrack: (category: ConsentCategory) => boolean;
}
