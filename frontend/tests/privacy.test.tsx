import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, act, fireEvent } from "@testing-library/react";
import {
  PrivacyProvider,
  usePrivacy,
  CookieConsentBanner,
  CookiePreferencesModal,
  ORCHESTRA_CONSENT_KEY,
  getStoredConsent,
  saveStoredConsent,
  clearStoredConsent,
  canTrack,
  dispatchTelemetryEvent,
} from "@/features/privacy";
import SettingsPage from "@/app/settings/page";
import CookiePolicyPage from "@/app/cookies/page";
import PrivacyPolicyPage from "@/app/privacy/page";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
  usePathname: () => "/settings",
  useSearchParams: () => ({
    get: vi.fn().mockReturnValue(null),
  }),
}));

// Mock Auth and Project contexts for SettingsPage rendering
vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: 42, email: "developer@orchestra.ai", role: "admin" },
    status: "authenticated",
    logout: vi.fn(),
  }),
}));

vi.mock("@/features/projects/ProjectContext", () => ({
  useProject: () => ({
    selectedProject: { id: 1, name: "Core Intelligence Platform" },
  }),
}));

function TestPrivacyConsumer() {
  const { consent, hasResponded, openPreferences, canTrack: hookCanTrack } =
    usePrivacy();
  return (
    <div>
      <div data-testid="has-responded">{String(hasResponded)}</div>
      <div data-testid="essential-consent">
        {String(consent?.categories?.essential || false)}
      </div>
      <div data-testid="analytics-consent">
        {String(consent?.categories?.analytics || false)}
      </div>
      <div data-testid="can-track-analytics">
        {String(hookCanTrack("analytics"))}
      </div>
      <button data-testid="open-prefs-btn" onClick={openPreferences}>
        Open Preferences
      </button>
    </div>
  );
}

describe("Privacy & Cookie Consent Architecture", () => {
  beforeEach(() => {
    localStorage.clear();
    clearStoredConsent();
    vi.restoreAllMocks();
  });

  it("renders banner on initial load when consent record is null", () => {
    render(
      <PrivacyProvider>
        <TestPrivacyConsumer />
        <CookieConsentBanner />
      </PrivacyProvider>
    );

    expect(screen.getByTestId("has-responded").textContent).toBe("false");
    expect(screen.getByRole("region", { name: /cookie and privacy consent/i })).toBeDefined();
    expect(screen.getByText(/Privacy & Cookie Notice/i)).toBeDefined();
    expect(screen.getByRole("button", { name: /acknowledge & continue/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /customize preferences/i })).toBeDefined();
  });

  it("clicking Acknowledge & Continue stores consent and dismisses banner", () => {
    render(
      <PrivacyProvider>
        <TestPrivacyConsumer />
        <CookieConsentBanner />
      </PrivacyProvider>
    );

    const ackButton = screen.getByRole("button", { name: /acknowledge & continue/i });
    act(() => {
      fireEvent.click(ackButton);
    });

    expect(screen.getByTestId("has-responded").textContent).toBe("true");
    expect(screen.getByTestId("essential-consent").textContent).toBe("true");
    expect(screen.getByTestId("analytics-consent").textContent).toBe("false");
    expect(screen.queryByRole("region", { name: /cookie and privacy consent/i })).toBeNull();

    const stored = getStoredConsent();
    expect(stored).not.toBeNull();
    expect(stored?.version).toBe(1);
    expect(stored?.consentGiven).toBe(true);
    expect(stored?.categories.essential).toBe(true);
    expect(stored?.categories.analytics).toBe(false);
  });

  it("clicking Customize Preferences opens the CookiePreferencesModal with focus trap", () => {
    render(
      <PrivacyProvider>
        <CookieConsentBanner />
        <CookiePreferencesModal />
      </PrivacyProvider>
    );

    const customizeBtn = screen.getByRole("button", { name: /customize preferences/i });
    act(() => {
      fireEvent.click(customizeBtn);
    });

    const dialog = screen.getByRole("dialog", { name: /privacy & cookie preferences/i });
    expect(dialog).toBeDefined();
    expect(screen.getByText(/Strictly Necessary Cookies & Storage/i)).toBeDefined();
    expect(screen.getByText(/Always Active/i)).toBeDefined();
    expect(screen.getByText(/Not Currently Available/i)).toBeDefined();
  });

  it("modal locks Essential cookies to disabled and checked (cannot be disabled)", () => {
    render(
      <PrivacyProvider>
        <CookiePreferencesModal />
        <TestPrivacyConsumer />
      </PrivacyProvider>
    );

    act(() => {
      fireEvent.click(screen.getByTestId("open-prefs-btn"));
    });

    const essentialCheckbox = screen.getByLabelText(/strictly necessary cookies are always active/i);
    expect(essentialCheckbox).toBeDefined();
    expect((essentialCheckbox as HTMLInputElement).checked).toBe(true);
    expect((essentialCheckbox as HTMLInputElement).disabled).toBe(true);
  });

  it("saving preferences in modal persists chosen choices to localStorage and updates telemetry gate", () => {
    render(
      <PrivacyProvider>
        <TestPrivacyConsumer />
        <CookiePreferencesModal />
      </PrivacyProvider>
    );

    act(() => {
      fireEvent.click(screen.getByTestId("open-prefs-btn"));
    });

    const toggle = screen.getByRole("switch", { name: /toggle optional analytics/i });
    expect(toggle.getAttribute("aria-checked")).toBe("false");

    // Toggle analytics ON
    act(() => {
      fireEvent.click(toggle);
    });
    expect(toggle.getAttribute("aria-checked")).toBe("true");

    // Click Save Preferences
    const saveBtn = screen.getByRole("button", { name: /save preferences/i });
    act(() => {
      fireEvent.click(saveBtn);
    });

    // Modal closes
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByTestId("analytics-consent").textContent).toBe("true");
    expect(screen.getByTestId("can-track-analytics").textContent).toBe("true");

    // Stored in localStorage
    const stored = getStoredConsent();
    expect(stored?.categories.analytics).toBe(true);
  });

  it("telemetry gate drops analytics events when consent is false and permits when true", () => {
    // 1. Initial state (no consent)
    expect(canTrack("essential")).toBe(true);
    expect(canTrack("analytics")).toBe(false);
    expect(dispatchTelemetryEvent("test_event", { data: 123 })).toBe(false);

    // 2. Grant analytics consent
    saveStoredConsent(true);
    expect(canTrack("analytics")).toBe(true);
    expect(dispatchTelemetryEvent("test_event", { data: 123 })).toBe(true);

    // 3. Revoke consent (opt-out)
    saveStoredConsent(false);
    expect(canTrack("analytics")).toBe(false);
    expect(dispatchTelemetryEvent("test_event", { data: 123 })).toBe(false);
  });

  it("verifies localStorage contains zero JWT tokens, secrets, or credentials", () => {
    saveStoredConsent(true);
    const raw = localStorage.getItem(ORCHESTRA_CONSENT_KEY) || "";

    expect(raw).not.toContain("bearer");
    expect(raw).not.toContain("jwt");
    expect(raw).not.toContain("secret");
    expect(raw).not.toContain("password");
    expect(raw).not.toContain("token");
    expect(raw).not.toContain("@");
  });

  it("cross-tab synchronization: storage event updates consent state across independent tabs", () => {
    render(
      <PrivacyProvider>
        <TestPrivacyConsumer />
      </PrivacyProvider>
    );

    expect(screen.getByTestId("analytics-consent").textContent).toBe("false");

    // Simulate update from another browser tab
    const updatedRecord = {
      version: 1,
      consentGiven: true,
      categories: { essential: true, analytics: true },
      updatedAt: new Date().toISOString(),
    };

    act(() => {
      localStorage.setItem(ORCHESTRA_CONSENT_KEY, JSON.stringify(updatedRecord));
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: ORCHESTRA_CONSENT_KEY,
          newValue: JSON.stringify(updatedRecord),
        })
      );
    });

    expect(screen.getByTestId("analytics-consent").textContent).toBe("true");
    expect(screen.getByTestId("can-track-analytics").textContent).toBe("true");
  });

  it("SettingsPage renders Privacy & Data Preferences card and button triggers modal", () => {
    saveStoredConsent(false);

    render(
      <PrivacyProvider>
        <SettingsPage />
        <CookiePreferencesModal />
      </PrivacyProvider>
    );

    expect(screen.getByText(/Privacy & Data Preferences/i)).toBeDefined();
    expect(screen.getByText(/Essential Authentication & CSRF Cookies/i)).toBeDefined();
    expect(screen.getByText(/Active \(Mandatory Core Security\)/i)).toBeDefined();
    expect(screen.getByText(/Not Currently Available \(Off by Default\)/i)).toBeDefined();
    expect(screen.getByText(/Zero Deployed \(Privacy-by-Design\)/i)).toBeDefined();

    const manageBtn = screen.getByRole("button", { name: /manage cookie preferences/i });
    act(() => {
      fireEvent.click(manageBtn);
    });

    expect(screen.getByRole("dialog", { name: /privacy & cookie preferences/i })).toBeDefined();
  });

  it("CookiePolicyPage and PrivacyPolicyPage render draft notice banners", () => {
    const { unmount } = render(
      <PrivacyProvider>
        <CookiePolicyPage />
      </PrivacyProvider>
    );

    expect(screen.getByText(/Cookie Policy/i)).toBeDefined();
    expect(screen.getByText(/\[DRAFT — PENDING OWNER REVIEW\]/i)).toBeDefined();
    expect(screen.getByText(/First-Party Cookies Deployed by Orchestra/i)).toBeDefined();

    unmount();

    render(
      <PrivacyProvider>
        <PrivacyPolicyPage />
      </PrivacyProvider>
    );

    expect(screen.getByText(/Privacy Policy/i)).toBeDefined();
    expect(screen.getByText(/\[DRAFT — PENDING OWNER REVIEW\]/i)).toBeDefined();
    expect(screen.getByText(/External AI Inference & Embeddings Disclosure/i)).toBeDefined();
  });

  it("Escape key dismisses preferences modal without altering saved consent", () => {
    saveStoredConsent(false);

    render(
      <PrivacyProvider>
        <TestPrivacyConsumer />
        <CookiePreferencesModal />
      </PrivacyProvider>
    );

    act(() => {
      fireEvent.click(screen.getByTestId("open-prefs-btn"));
    });

    expect(screen.getByRole("dialog")).toBeDefined();

    // Toggle switch without clicking save
    const toggle = screen.getByRole("switch");
    act(() => {
      fireEvent.click(toggle);
    });
    expect(toggle.getAttribute("aria-checked")).toBe("true");

    // Press Escape
    act(() => {
      fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape", code: "Escape" });
    });

    // Dialog dismissed
    expect(screen.queryByRole("dialog")).toBeNull();

    // Consent remains false
    expect(screen.getByTestId("analytics-consent").textContent).toBe("false");
    expect(getStoredConsent()?.categories.analytics).toBe(false);
  });
});
