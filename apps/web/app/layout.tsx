import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "refle",
  description: "AI-Powered Automated Compliance for your Business",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
