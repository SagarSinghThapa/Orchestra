import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/features/auth/AuthContext";
import { AppShell } from "@/components/layout/AppShell";
import {
  PrivacyProvider,
  CookieConsentBanner,
  CookiePreferencesModal,
} from "@/features/privacy";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Orchestra — Multi-Agent AI Platform",
  description: "Autonomous Multi-Agent AI Engineering & Research Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} bg-gray-50 text-gray-900`} suppressHydrationWarning>
        <AuthProvider>
          <PrivacyProvider>
            <AppShell>{children}</AppShell>
            <CookieConsentBanner />
            <CookiePreferencesModal />
          </PrivacyProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
