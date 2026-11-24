import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Strategy lab — systematic strategy research",
  description:
    "A visual research portal for systematic strategies: equity curves, drawdowns, yearly and monthly returns, trade statistics and the exact rules.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
