import React from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { getPolicyGovernanceStatus } from "@/features/privacy/governance";

export const metadata = {
  title: "Privacy Policy (Draft) — Orchestra",
  description: "Verified data processing and privacy architecture for the Orchestra Platform.",
};

export default function PrivacyPolicyPage() {
  const governance = getPolicyGovernanceStatus();

  return (
    <div className="min-h-screen bg-[#101014] text-[#F5F5F5] py-12 px-4 sm:px-8">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Navigation link */}
        <div className="flex items-center justify-between">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-xs font-medium text-[#8B7CFF] hover:text-[#A599FF] transition"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back to Orchestra
          </Link>
          <Link
            href="/cookies"
            className="text-xs font-medium text-[#A4A6B8] hover:text-white transition"
          >
            View Cookie Policy &rarr;
          </Link>
        </div>

        {/* Header */}
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-2">
            <h1 className="text-3xl sm:text-4xl font-extrabold text-[#F8F8FC] tracking-tight">
              Privacy Policy
            </h1>
            <span className="text-xs font-mono text-[#A4A6B8]">
              Effective Date: {governance.effectiveDate}
            </span>
          </div>
          <p className="text-sm text-[#A4A6B8]">
            Technical architecture and empirical data governance disclosures.
          </p>
        </div>

        {/* Draft Notice Banner (strictly enforced until 3-gate owner sign-off) */}
        {governance.isDraft && (
          <div
            role="alert"
            className="p-4 sm:p-5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs sm:text-sm space-y-1"
          >
            <div className="flex items-center gap-2 font-bold font-mono uppercase tracking-wider text-amber-300">
              <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              {governance.statusLabel}
            </div>
            <p className="text-amber-200/90 leading-relaxed">
              This document reflects verified static codebase analysis and documented infrastructure
              for Orchestra. It must be formally reviewed and approved by the platform owner or legal
              counsel before official publication. Automatic publication via environment variables alone
              is strictly prohibited.
            </p>
          </div>
        )}

        {/* Section 1: Overview */}
        <Card>
          <h2 className="text-base sm:text-lg font-bold text-[#F8F8FC] mb-3 border-b border-white/[0.08] pb-2">
            1. Platform Overview &amp; Data Philosophy
          </h2>
          <p className="text-xs sm:text-sm text-[#A4A6B8] leading-relaxed">
            Orchestra is an autonomous multi-agent engineering and research platform. It operates
            with strict technical tenancy boundaries. Customer documents, chat sessions, and
            code repositories are isolated by project identifiers. Orchestra does not monetize
            personal information, sell user data to data brokers, or deploy third-party advertising
            networks.
          </p>
        </Card>

        {/* Section 2: Data Collected & Stored */}
        <Card>
          <h2 className="text-base sm:text-lg font-bold text-[#F8F8FC] mb-3 border-b border-white/[0.08] pb-2">
            2. Data Categories &amp; Storage Infrastructure
          </h2>
          <div className="space-y-4 text-xs sm:text-sm text-[#A4A6B8]">
            <div>
              <h3 className="font-semibold text-[#F8F8FC] mb-1">A. Authentication Credentials</h3>
              <p className="leading-relaxed">
                User accounts require an email address and password. Passwords are never stored in
                plaintext; they are salted and hashed using bcrypt via Passlib prior to database
                persistence. Authentication state is maintained using JWT tokens stored in
                browser-restricted, HttpOnly, SameSite=Lax cookies.
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-[#F8F8FC] mb-1">B. Research Documents &amp; Artifacts</h3>
              <p className="leading-relaxed">
                Users may upload technical documents in <code className="text-[#8B7CFF]">.pdf</code>,{" "}
                <code className="text-[#8B7CFF]">.txt</code>, and{" "}
                <code className="text-[#8B7CFF]">.md</code> formats (capped at 10 MB). Ingestion
                extracts raw text into chunked fragments stored with deterministic UUIDv5 identifiers in
                a self-hosted Qdrant vector database.
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-[#F8F8FC] mb-1">C. Chat Messages &amp; Agent Workspaces</h3>
              <p className="leading-relaxed">
                Prompts, generated code patches, unified diffs, and research responses are stored in
                the relational PostgreSQL database under the user&apos;s active project tenancy. Conversation
                memory is incrementally summarized to prevent token overflow.
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-[#F8F8FC] mb-1">D. Relational &amp; Cache Infrastructure</h3>
              <ul className="list-disc pl-5 space-y-1 mt-1 text-[#A4A6B8]">
                <li><strong className="text-[#F8F8FC]">PostgreSQL 16:</strong> Durable store for accounts, projects, sessions, messages, documents, and evaluation runs.</li>
                <li><strong className="text-[#F8F8FC]">Redis 7:</strong> Real-time session token revocation blocklist and sliding-window rate limiting.</li>
                <li><strong className="text-[#F8F8FC]">Qdrant v1.12.5:</strong> Dense vector store for semantic similarity and citation verification.</li>
              </ul>
            </div>
          </div>
        </Card>

        {/* Section 3: External AI Inference */}
        <Card>
          <h2 className="text-base sm:text-lg font-bold text-[#F8F8FC] mb-3 border-b border-white/[0.08] pb-2">
            3. External AI Inference &amp; Embeddings Disclosure
          </h2>
          <div className="space-y-3 text-xs sm:text-sm text-[#A4A6B8] leading-relaxed">
            <p>
              To execute multi-agent research planning, code generation, and semantic vector indexing,
              the Orchestra backend dispatches prompts and document chunks to operator-configured
              model APIs:
            </p>
            <ul className="list-disc pl-5 space-y-1 text-[#A4A6B8]">
              <li>
                <strong className="text-[#F8F8FC]">NVIDIA NIM API:</strong> Generates 2048-dimensional
                dense embeddings (e.g. <code className="text-[#8B7CFF]">nvidia/nemotron-3.5-embed-1b</code>)
                via secure HTTPS calls to <code className="text-[#8B7CFF]">https://integrate.api.nvidia.com/v1</code>.
              </li>
              <li>
                <strong className="text-[#F8F8FC]">OpenAI-Compatible Providers:</strong> Generates structured
                JSON responses for research synthesis and coding agent execution.
              </li>
            </ul>
            <p>
              API keys and service credentials remain exclusively in server environment variables. They
              are never exposed to the client or transmitted across public networks.
            </p>
          </div>
        </Card>

        {/* Section 4: User Controls & Deletion */}
        <Card>
          <h2 className="text-base sm:text-lg font-bold text-[#F8F8FC] mb-3 border-b border-white/[0.08] pb-2">
            4. User Controls &amp; Data Management Rights
          </h2>
          <div className="space-y-3 text-xs sm:text-sm text-[#A4A6B8] leading-relaxed">
            <p>
              Orchestra provides granular self-service control over data:
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong className="text-[#F8F8FC]">Session Termination:</strong> Logging out immediately revokes your active access and refresh token IDs in Redis.</li>
              <li><strong className="text-[#F8F8FC]">Document Deletion:</strong> Deleting a document removes its database record and purges all corresponding vector points from Qdrant.</li>
              <li><strong className="text-[#F8F8FC]">Project Cascade:</strong> Deleting a project cascades and removes associated sessions, messages, and document associations.</li>
            </ul>
          </div>
        </Card>
      </div>
    </div>
  );
}
