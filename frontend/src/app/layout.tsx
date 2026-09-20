import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ProGrapher",
  description: "ProGrapher V2 Desktop",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="he" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
