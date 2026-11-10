import type { Metadata } from "next";
import { Archivo, Martian_Mono } from "next/font/google";
import "./globals.css";

// Archivo's width axis gives one family two voices: expanded for headlines,
// normal width for reading. Martian Mono sets figures, ids and labels.
const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  axes: ["wdth"],
});

const martian = Martian_Mono({
  variable: "--font-martian",
  subsets: ["latin"],
  axes: ["wdth"],
});

export const metadata: Metadata = {
  title: "Fineprint · Every dollar, cleared by the clause",
  description:
    "Fineprint reads grant agreements and expense policies into rules quoted from the document, then checks every expense against them before it's paid.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${archivo.variable} ${martian.variable} font-sans antialiased`}>{children}</body>
    </html>
  );
}
