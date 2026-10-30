import { describe, it, expect } from "vitest";
import React from "react";
import { render } from "@testing-library/react";
import { SafeMarkdown } from "@/components/chat/SafeMarkdown";
import { UnifiedDiffViewer } from "@/components/developer/UnifiedDiffViewer";

describe("Frontend Security, XSS Immunity & Sanitization", () => {
  it("neutralizes script tags and harmful HTML in SafeMarkdown", () => {
    const maliciousInput = `# Header

<script>alert('pwned')</script>

<iframe src="https://evil.com"></iframe>

Safe text remains.`;

    const { container } = render(<SafeMarkdown content={maliciousInput} />);

    // Script, iframe attributes must not exist in DOM
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("iframe")).toBeNull();
    expect(container.textContent).toContain("Safe text remains.");
    expect(container.textContent).not.toContain("alert('pwned')");
  });

  it("disallows dangerous javascript: link protocols", () => {
    const dangerousLinks = `
[Click me](javascript:alert(1))
[Safe Link](https://orchestra.ai)
    `;

    const { container } = render(<SafeMarkdown content={dangerousLinks} />);

    const links = container.querySelectorAll("a");
    // Dangerous javascript: link should be neutralized to a span without href or sanitized
    const jsLink = Array.from(links).find((a) => a.getAttribute("href")?.includes("javascript:"));
    expect(jsLink).toBeUndefined();

    // Safe link preserved with target="_blank" and rel="noopener noreferrer"
    const safeLink = Array.from(links).find((a) => a.getAttribute("href") === "https://orchestra.ai");
    expect(safeLink).toBeDefined();
    expect(safeLink?.getAttribute("target")).toBe("_blank");
    expect(safeLink?.getAttribute("rel")).toContain("noopener");
  });

  it("renders unified diff text as inert text nodes avoiding HTML injection", () => {
    const maliciousDiff = `--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-<script>alert("diff_xss")</script>
+<b onmouseover="alert(1)">safe bold</b>`;

    const { container } = render(<UnifiedDiffViewer diff={maliciousDiff} path="file.py" />);

    // No interactive HTML tags should be parsed inside the diff table
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain('<script>alert("diff_xss")</script>');
  });
});
