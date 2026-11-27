"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  h1: ({ children }) => (
    <h2 className="mt-6 text-xl font-semibold text-zinc-100">{children}</h2>
  ),
  h2: ({ children }) => (
    <h3 className="mt-6 text-[17px] font-semibold text-zinc-100">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="mt-5 text-[14px] font-semibold text-zinc-200">{children}</h4>
  ),
  h4: ({ children }) => (
    <h5 className="mt-4 text-[13px] font-semibold text-zinc-200">{children}</h5>
  ),
  p: ({ children }) => (
    <p className="mt-3 text-[12.5px] leading-relaxed text-zinc-400">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mt-3 list-disc space-y-1.5 pl-5 text-[12.5px] leading-relaxed text-zinc-400">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-[12.5px] leading-relaxed text-zinc-400">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="pl-1">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-zinc-200">{children}</strong>
  ),
  em: ({ children }) => <em className="text-zinc-300">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-emerald-200 underline decoration-emerald-200/30 underline-offset-2 transition hover:decoration-emerald-200"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mt-3 border-l-2 border-emerald-300/30 pl-3 text-[12px] leading-relaxed text-zinc-500">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-5 border-white/[0.06]" />,
  table: ({ children }) => (
    <div className="mt-3 overflow-x-auto rounded-lg border border-white/[0.06]">
      <table className="w-full border-collapse text-left text-[11.5px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-white/[0.03] text-zinc-300">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-white/10 px-2.5 py-2 font-medium">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border-b border-white/[0.05] px-2.5 py-2 align-top text-zinc-400">
      {children}
    </td>
  ),
  pre: ({ children }) => (
    <pre className="mt-3 overflow-x-auto rounded-lg border border-white/[0.06] bg-black/30 p-3 text-[11.5px] leading-relaxed text-zinc-300">
      {children}
    </pre>
  ),
  code: ({ className, children }) => {
    const block = Boolean(className && className.includes("language-"));
    if (block) return <code className="block">{children}</code>;
    return (
      <code className="rounded bg-white/[0.06] px-1 py-0.5 text-[0.92em] text-zinc-200">
        {children}
      </code>
    );
  },
};

export function Markdown({
  children,
  className = "",
}: {
  children: string;
  className?: string;
}) {
  if (!children) return null;
  return (
    <div className={`max-w-none ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
