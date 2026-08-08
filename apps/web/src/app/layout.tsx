import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Report Intelligence",
  description: "הופך דוח כספי לסיפור פיננסי שניתן לבדוק.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  // The product is Hebrew-first, so the document is right-to-left from the start.
  // A localisation library is deliberately deferred until phase 5.
  return (
    <html lang="he" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
