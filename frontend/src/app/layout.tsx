import "./globals.css";

export const metadata = {
  title: "ProGrapher",
  description: "פאנל עבודה חכם לעריכת תמונות לצלמי אירועים",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
