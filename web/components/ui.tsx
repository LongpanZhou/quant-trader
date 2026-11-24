import type { ReactNode } from "react";

export function LogoMark({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" rx="9" fill="#0f1114" stroke="#2a3037" />
      <path d="M7 21.5 12.3 16l4.2 3.4L25 9.5" fill="none" stroke="#9ae6a5" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="25" cy="9.5" r="2.1" fill="#9ae6a5" />
    </svg>
  );
}

export function Pill({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "red" | "blue" | "amber";
  className?: string;
}) {
  const tones = {
    neutral: "border-white/10 bg-white/[0.03] text-zinc-400",
    green: "border-emerald-300/20 bg-emerald-300/[0.07] text-emerald-200",
    red: "border-rose-300/20 bg-rose-300/[0.07] text-rose-200",
    blue: "border-sky-300/20 bg-sky-300/[0.07] text-sky-200",
    amber: "border-amber-300/20 bg-amber-300/[0.07] text-amber-200",
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.14em] ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function StatCard({
  label,
  value,
  sub,
  tone = "neutral",
  className = "",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "green" | "red" | "blue";
  className?: string;
}) {
  const colors = {
    neutral: "text-zinc-100",
    green: "text-emerald-200",
    red: "text-rose-200",
    blue: "text-sky-200",
  } as const;
  return (
    <div className={`panel-soft flex min-h-[118px] flex-col justify-between p-4 ${className}`}>
      <div className="eyebrow">{label}</div>
      <div>
        <div className={`stat-value text-[1.55rem] font-semibold leading-none ${colors[tone]}`}>
          {value}
        </div>
        {sub ? <div className="mt-2 text-[11px] leading-snug text-zinc-500">{sub}</div> : null}
      </div>
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  right,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  right?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <div className="eyebrow mb-2">{eyebrow}</div>
        <h2 className="display text-2xl font-semibold text-zinc-100 sm:text-[1.7rem]">{title}</h2>
        {description ? (
          <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-zinc-500">{description}</p>
        ) : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}

export function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-zinc-500">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`panel ${className}`}>{children}</div>;
}
