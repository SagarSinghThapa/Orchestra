"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

interface SafeMarkdownProps {
  content: string;
}

export function SafeMarkdown({ content }: SafeMarkdownProps) {
  return (
    <div className="prose prose-invert prose-sm max-w-none text-[#F5F5F5] break-words" data-testid="message-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[
          [
            rehypeSanitize,
            {
              ...defaultSchema,
              attributes: {
                ...defaultSchema.attributes,
                a: [
                  ...(defaultSchema.attributes?.a || []),
                  ["target", "_blank"],
                  ["rel", "noopener noreferrer"],
                ],
              },
            },
          ],
        ]}
        components={{
          a: ({ href, children, ...props }) => {
            // Guard against unsafe link protocols
            const isSafe = href && (href.startsWith("http://") || href.startsWith("https://"));
            if (!isSafe) {
              return <span>{children}</span>;
            }
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#8B7CFF] underline hover:text-[#5146FF]"
                {...props}
              >
                {children}
              </a>
            );
          },
          pre: ({ children, ...props }) => (
            <pre
              className="bg-[#20212B] text-[#F5F5F5] p-3 rounded-xl border border-white/[0.08] overflow-x-auto my-2 text-xs font-mono"
              {...props}
            >
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }) => {
            const isInline = !className;
            return isInline ? (
              <code
                className="bg-[#20212B] text-[#8B7CFF] px-1.5 py-0.5 rounded text-xs font-mono border border-white/[0.08]"
                {...props}
              >
                {children}
              </code>
            ) : (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
