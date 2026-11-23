import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import PrivacyPolicyPage from "@/app/privacy/page";
import CookiePolicyPage from "@/app/cookies/page";
import {
  getPolicyGovernanceStatus,
  POLICY_GOVERNANCE_CONFIG,
} from "@/features/privacy/governance";
import { PrivacyProvider } from "@/features/privacy";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
  usePathname: () => "/privacy",
  useSearchParams: () => ({
    get: vi.fn().mockReturnValue(null),
  }),
}));

describe("Multi-Gate Privacy Policy Governance", () => {
  beforeEach(() => {
    // Reset governance config to default draft state
    POLICY_GOVERNANCE_CONFIG.ownerSignoffCompleted = false;
    POLICY_GOVERNANCE_CONFIG.codebaseVerified = true;
    POLICY_GOVERNANCE_CONFIG.approvedEffectiveDate = null;
  });

  it("defaults to Draft state with explicit review pending label", () => {
    const status = getPolicyGovernanceStatus();
    expect(status.isDraft).toBe(true);
    expect(status.statusLabel).toBe("[DRAFT — PENDING OWNER REVIEW]");
    expect(status.effectiveDate).toBe("Pending Formal Owner Review");
  });

  it("prohibits publication through environment variable alone", () => {
    // Simulate setting an environment variable
    vi.stubEnv("NEXT_PUBLIC_POLICY_PUBLISHED", "true");

    const status = getPolicyGovernanceStatus();
    // Must STILL be draft because Gate 1 (Owner review) and Gate 3 (Effective date) are not met
    expect(status.isDraft).toBe(true);
    expect(status.statusLabel).toBe("[DRAFT — PENDING OWNER REVIEW]");

    vi.unstubAllEnvs();
  });

  it("remains in Draft if owner sign-off is completed but approved effective date is missing", () => {
    POLICY_GOVERNANCE_CONFIG.ownerSignoffCompleted = true;
    POLICY_GOVERNANCE_CONFIG.approvedEffectiveDate = null;

    const status = getPolicyGovernanceStatus();
    expect(status.isDraft).toBe(true);
    expect(status.statusLabel).toBe("[DRAFT — PENDING OWNER REVIEW]");
  });

  it("remains in Draft if effective date exists but owner sign-off is false", () => {
    POLICY_GOVERNANCE_CONFIG.ownerSignoffCompleted = false;
    POLICY_GOVERNANCE_CONFIG.approvedEffectiveDate = "2026-11-22";

    const status = getPolicyGovernanceStatus();
    expect(status.isDraft).toBe(true);
    expect(status.statusLabel).toBe("[DRAFT — PENDING OWNER REVIEW]");
  });

  it("evaluates to published only when all three gates are formally satisfied", () => {
    POLICY_GOVERNANCE_CONFIG.ownerSignoffCompleted = true;
    POLICY_GOVERNANCE_CONFIG.codebaseVerified = true;
    POLICY_GOVERNANCE_CONFIG.approvedEffectiveDate = "2026-11-22";

    const status = getPolicyGovernanceStatus();
    expect(status.isDraft).toBe(false);
    expect(status.statusLabel).toBe("Official Policy");
    expect(status.effectiveDate).toBe("2026-11-22");
  });

  it("renders Draft banner in PrivacyPolicyPage by default", () => {
    render(<PrivacyPolicyPage />);
    const draftAlert = screen.getByRole("alert");
    expect(draftAlert).toBeInTheDocument();
    expect(draftAlert).toHaveTextContent("[DRAFT — PENDING OWNER REVIEW]");
    expect(screen.getByText(/Effective Date: Pending Formal Owner Review/i)).toBeInTheDocument();
  });

  it("renders Draft banner in CookiePolicyPage by default", () => {
    render(
      <PrivacyProvider>
        <CookiePolicyPage />
      </PrivacyProvider>
    );
    const draftAlert = screen.getByRole("alert");
    expect(draftAlert).toBeInTheDocument();
    expect(draftAlert).toHaveTextContent("[DRAFT — PENDING OWNER REVIEW]");
    expect(screen.getByText(/Effective Date: Pending Formal Owner Review/i)).toBeInTheDocument();
  });
});
