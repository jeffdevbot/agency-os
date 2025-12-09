import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { PosthogProvider } from "./posthog-provider";
import { PosthogIdentify } from "./posthog-identify";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Ecomlabs Tools — Secure Sign In",
  description: "Sign in to access the Ecomlabs Tools dashboard and internal tools.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <PosthogProvider />
        <PosthogIdentify />
        {children}
      </body>
    </html>
  );
}
