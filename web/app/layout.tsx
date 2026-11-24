import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nasdaq Leveraged Trend — strategy dashboard",
  description:
    "A visual research dashboard for a volatility-targeted QQQ/TQQQ trend strategy: equity curve, drawdowns, yearly returns, trade statistics and the exact code.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
