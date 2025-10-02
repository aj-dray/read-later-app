import "@/app/_ui/globals.css";
import PanelGate from "@/app/_components/PanelGate";
import { getSession } from "@/app/_lib/auth";
import { getCurrentUser } from "@/app/_lib/user";
import { preloadAllAppSettings } from "@/app/_lib/user-controls-server";
import { SettingsProvider } from "@/app/_contexts/SettingsContext";
import { ClusterProvider } from "@/app/_contexts/ClusterContext";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { headers } from "next/headers";

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-plex-mono",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export default async function RootLayout({
  children,
  controls,
}: Readonly<{ children: React.ReactNode; controls?: React.ReactNode }>) {
  const session = await getSession();
  const user = session ? await getCurrentUser() : null;
  const initialSettings = user ? await preloadAllAppSettings() : {};

  return (
    <html lang="en" className={`${ibmPlexMono.variable} ${inter.variable}`}>
      <body>
        <SettingsProvider initialSettings={initialSettings}>
          <ClusterProvider>
            <div className="relative h-screen w-screen">
              {/* main content */}
              <div className="h-full w-full">{children}</div>

              {/* overlay panel - only show when user is authenticated and not on mobile */}
              {user && (
                <div className="pointer-events-none absolute inset-0">
                  <div className="pointer-events-auto">
                    <PanelGate session={user}>{controls}</PanelGate>
                  </div>
                </div>
              )}
            </div>
          </ClusterProvider>
        </SettingsProvider>
        <Analytics />
      </body>
    </html>
  );
}
