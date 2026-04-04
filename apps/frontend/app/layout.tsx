import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
  title: "KZ8A Live Monitor",
  description: "Telemetry pipeline MVP stage 1"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
