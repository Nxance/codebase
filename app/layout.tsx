import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nxance — Your investment workspace",
  description: "Sign in to Nxance to understand your portfolio and save your goal plans.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
