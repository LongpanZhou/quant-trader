"use client";

import { usePathname } from "next/navigation";
import { LogoMark } from "./ui";

const REPO = "https://github.com/LongpanZhou/quant-trader";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/compare", label: "All strategies" },
  { href: "/research", label: "Research library" },
  { href: "/lab", label: "Backtest lab" },
];

export function SiteHeader({
  mode = "catalog",
}: {
  mode?: "catalog" | "strategy" | "lab";
}) {
  const pathname = usePathname() || (mode === "lab" ? "/lab" : mode === "strategy" ? "/" : "/");
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-[#08090b]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1180px] items-center justify-between px-5 lg:px-8">
        <a href="/" className="flex min-w-0 items-center gap-2.5">
          <LogoMark className="h-7 w-7" />
          <span className="text-[13px] font-semibold tracking-[-0.01em] text-zinc-200">
            quant-trader
            <span className="ml-2 hidden text-[11px] font-normal text-zinc-600 sm:inline">
              research portal
            </span>
          </span>
        </a>
        <nav className="hidden items-center gap-6 text-[11px] md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={`transition ${
                isActive(link.href)
                  ? "text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-200"
              }`}
              aria-current={isActive(link.href) ? "page" : undefined}
            >
              {link.label}
            </a>
          ))}
        </nav>
        <a
          href={REPO}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-[10px] uppercase tracking-[0.14em] text-zinc-400 transition hover:border-white/20 hover:text-zinc-100"
        >
          GitHub
          <span aria-hidden="true">↗</span>
        </a>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="relative border-t border-white/[0.06]">
      <div className="mx-auto flex max-w-[1180px] flex-col gap-3 px-5 py-8 text-[11px] text-zinc-600 sm:flex-row sm:items-center sm:justify-between lg:px-8">
        <div>
          <span className="text-zinc-400">quant-trader</span> · paper trading only · not investment
          advice
        </div>
        <div className="flex items-center gap-4">
          <span>Data: Yahoo Finance</span>
          <a className="transition hover:text-zinc-300" href={REPO} target="_blank" rel="noreferrer">
            Source ↗
          </a>
        </div>
      </div>
    </footer>
  );
}
