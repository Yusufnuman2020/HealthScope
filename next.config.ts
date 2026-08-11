import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export", // GitHub Pages statik site istediği için bu şart
  basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "/HealthScope",
  images: {
    unoptimized: true, // Statik exportta resim optimizasyonu çalışmaz
  },
  turbopack: {
    // Kök dizin elle sabitlenir. Aksi hâlde Next, ev dizinindeki başıboş bir
    // package-lock.json yüzünden kökü C:\Users\<kullanıcı> olarak seçiyor ve
    // üretilen modül kimliğine Türkçe karakterli klasör adı ("tüm projelerim")
    // giriyor; bu da Turbopack'te bir UTF-8 sınır hatasına yol açıyor.
    root: __dirname,
  },
};

export default nextConfig;
