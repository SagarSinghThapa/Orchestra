/**
 * Strict Multi-Gate Policy Governance
 *
 * Mandate:
 * Policies can NEVER be automatically published through an environment variable alone.
 * Official publication strictly requires satisfying three gates simultaneously:
 * 1. Gate 1 (Owner Review): Formal sign-off completed in docs/compliance/OWNER_POLICY_REVIEW.md
 * 2. Gate 2 (Codebase Verified): Disclosures empirically verified against live code
 * 3. Gate 3 (Approved Effective Date): Non-empty effective date explicitly approved by the owner
 *
 * If any gate is unsatisfied, policies fail-safe to [DRAFT — PENDING OWNER REVIEW].
 */

export interface PolicyGovernanceStatus {
  isDraft: boolean;
  statusLabel: string;
  effectiveDate: string;
  ownerSignoffCompleted: boolean;
  codebaseVerified: boolean;
}

export const POLICY_GOVERNANCE_CONFIG = {
  // Gate 1: Formal owner review documented in docs/compliance/OWNER_POLICY_REVIEW.md
  ownerSignoffCompleted: false, // Default: false until owner formally signs off

  // Gate 2: Codebase empirical architecture verified
  codebaseVerified: true,

  // Gate 3: Approved effective date (must be non-null when published)
  approvedEffectiveDate: null as string | null,
};

export function getPolicyGovernanceStatus(): PolicyGovernanceStatus {
  // Strict multi-gate evaluation
  const isApproved =
    POLICY_GOVERNANCE_CONFIG.ownerSignoffCompleted === true &&
    POLICY_GOVERNANCE_CONFIG.codebaseVerified === true &&
    typeof POLICY_GOVERNANCE_CONFIG.approvedEffectiveDate === "string" &&
    POLICY_GOVERNANCE_CONFIG.approvedEffectiveDate.trim().length > 0;

  return {
    isDraft: !isApproved,
    statusLabel: isApproved ? "Official Policy" : "[DRAFT — PENDING OWNER REVIEW]",
    effectiveDate: isApproved
      ? (POLICY_GOVERNANCE_CONFIG.approvedEffectiveDate as string)
      : "Pending Formal Owner Review",
    ownerSignoffCompleted: POLICY_GOVERNANCE_CONFIG.ownerSignoffCompleted,
    codebaseVerified: POLICY_GOVERNANCE_CONFIG.codebaseVerified,
  };
}
