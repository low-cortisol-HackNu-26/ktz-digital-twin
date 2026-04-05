import type { Metadata } from "next";
import { JetBrains_Mono, Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const jetbrains = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KTZ Digital Twin — Railway dashboard",
  description: "Locomotive telemetry and health monitoring (frontend demo)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${jetbrains.variable} min-h-screen bg-black font-sans antialiased px-40`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
