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
    <div className="prose prose-sm max-w-none text-gray-800 break-words">
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
                className="text-blue-600 underline hover:text-blue-800"
                {...props}
              >
                {children}
              </a>
            );
          },
          pre: ({ children, ...props }) => (
            <pre
              className="bg-gray-900 text-gray-100 p-3 rounded-md overflow-x-auto my-2 text-xs font-mono"
              {...props}
            >
              {children}
            </pre>
          ),
          code: ({ className, children, ...props }) => {
            const isInline = !className;
            return isInline ? (
              <code
                className="bg-gray-100 text-red-600 px-1 py-0.5 rounded text-xs font-mono"
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
