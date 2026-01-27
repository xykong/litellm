import type { Metadata } from "next";
import "./globals.css";

<<<<<<< HEAD
import AntdGlobalProvider from "@/contexts/AntdGlobalProvider";
import { AuthProvider } from "@/contexts/AuthContext";
import ReactQueryProvider from "@/contexts/ReactQueryProvider";

const inter = Inter({ subsets: ["latin"] });

=======
>>>>>>> 285b35dd54 (fix(ui): remove Google Fonts dependency to avoid build timeout)
export const metadata: Metadata = {
  title: "Animal Gateway Dashboard",
  description: "Animal Gateway Proxy Admin UI",
  icons: { icon: "./favicon.ico" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
<<<<<<< HEAD
      <body className={inter.className}>
        <ReactQueryProvider>
          <AntdGlobalProvider>
            <AuthProvider>{children}</AuthProvider>
          </AntdGlobalProvider>
        </ReactQueryProvider>
      </body>
=======
      <body className="font-sans">{children}</body>
>>>>>>> 285b35dd54 (fix(ui): remove Google Fonts dependency to avoid build timeout)
    </html>
  );
}
