import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistPixelSquare } from "geist/font/pixel";
import { GeistSans } from "geist/font/sans";

import "./globals.css";

export const metadata: Metadata = {
  title: "Crucible Compute",
  description: "GPU deployment backend for personal agents.",
  icons: {
    icon: "/brand/crucible-logo.png",
    shortcut: "/brand/crucible-logo.png",
    apple: "/brand/crucible-logo.png"
  }
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} ${GeistPixelSquare.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
