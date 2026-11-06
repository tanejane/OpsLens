import type { Metadata } from "next";
import "./styles.css";
import "./business-overview.css";

export const metadata: Metadata = {
  title: "OpsLens — Operations intelligence",
  description: "A governed workspace for business investigations and operational evidence.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
