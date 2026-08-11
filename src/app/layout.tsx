import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import { themeInitScript } from "@/components/layout/ThemeToggle";

const inter = Inter({ subsets: ["latin", "latin-ext"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "HealthScope — Klinik Karar Destek Sistemi",
  description:
    "Kan tahlili parametrelerinden klinik çıkarım ve biyo-nutrisyonel öneri üreten karar destek sistemi.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <head>
        {/* Tema, hidrasyondan önce uygulanır — koyu tema tercihinde
            sayfanın önce beyaz açılıp sonra kararmasını engeller. */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={`${inter.variable} font-sans flex min-h-screen bg-surface text-ink antialiased`}>
        <Sidebar />
        {/* pt-[57px]: mobildeki sabit başlık çubuğunun kapladığı alan */}
        <main className="min-w-0 flex-1 pt-[57px] md:pt-0">
          <div className="mx-auto max-w-[1400px] px-5 py-7 md:px-9 md:py-9">{children}</div>
        </main>
      </body>
    </html>
  );
}
