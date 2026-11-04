import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "./auth-provider";

export const metadata: Metadata = {
  title: "Carbon ESG — Нүүрстөрөгчийн бүртгэл",
  description: "Байгууллагын хүлэмжийн хийн ялгарлыг хэмжих, тайлагнах платформ."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="mn">
      <body><AuthProvider>{children}</AuthProvider></body>
    </html>
  );
}
