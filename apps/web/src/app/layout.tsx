import type { Metadata } from "next";
import { Assistant, Frank_Ruhl_Libre } from "next/font/google";

import "./globals.css";

const frank = Frank_Ruhl_Libre({
  subsets: ["hebrew", "latin"],
  weight: ["400", "500", "700"],
  variable: "--font-frank",
  display: "swap",
});

const assistant = Assistant({
  subsets: ["hebrew", "latin"],
  weight: ["300", "400", "600"],
  variable: "--font-assistant",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Report Intelligence",
  description: "הופך דוח כספי לסיפור פיננסי שניתן לבדוק.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  // Hebrew-first, right to left from the document down. A localisation library
  // is still deliberately absent: there is one language, and adding a second
  // is a phase 7 decision.
  return (
    <html lang="he" dir="rtl" className={`${frank.variable} ${assistant.variable}`}>
      <body>{children}</body>
    </html>
  );
}
