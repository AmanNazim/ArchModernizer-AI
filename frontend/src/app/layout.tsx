import type { Metadata } from "next";
import "./globals.css";
import { JobStoreProvider } from "@/store/jobStore";

export const metadata: Metadata = {
  title: "ArchModernizer AI",
  description: "Legacy code modernization and cloud infrastructure optimization platform",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen antialiased">
        <JobStoreProvider>{children}</JobStoreProvider>
      </body>
    </html>
  );
}
