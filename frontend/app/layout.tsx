import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GASLIT — Operator Console (voice)",
  description: "LiveKit + ElevenLabs voice slice",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
