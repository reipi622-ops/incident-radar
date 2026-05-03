import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Incident Radar",
  description: "מעקב אירועים בזמן אמת",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="he" dir="rtl">
      <body className="bg-gray-950 text-gray-100 min-h-screen antialiased">
        <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
            <span className="font-bold text-lg tracking-tight text-white flex items-center gap-2">
              <span className="text-red-500">◉</span> Incident Radar
            </span>
            <div className="flex items-center gap-4 text-sm text-gray-400">
              <a href="/" className="hover:text-white transition-colors">דשבורד</a>
              <a href="/events" className="hover:text-white transition-colors">אירועים</a>
              <a href="/map" className="hover:text-white transition-colors">מפה</a>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
