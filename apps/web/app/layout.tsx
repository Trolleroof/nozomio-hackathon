import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Crucible Compute",
  description: "GPU deployment backend for personal agents."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
