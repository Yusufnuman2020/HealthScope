"use client";
import React from 'react';
import { Brain, Zap, Activity, Database, ArrowRight } from 'lucide-react';
import Link from 'next/link';

const StatCard = ({ title, value, subtext, icon: Icon, color }: any) => {
  // Tailwind'in dinamik sınıfları silmemesi için renk eşleştirmesi
  const colorMap: any = {
    blue: "bg-blue-500/10 text-blue-500",
    amber: "bg-amber-500/10 text-amber-500",
    emerald: "bg-emerald-500/10 text-emerald-500",
    purple: "bg-purple-500/10 text-purple-500"
  };

  return (
    <div className="bg-slate-900/40 border border-slate-800/60 p-6 rounded-[2rem] backdrop-blur-xl">
      <div className="flex justify-between items-start mb-4">
        <div className={`p-3 rounded-2xl ${colorMap[color] || colorMap.blue}`}>
          <Icon size={24} />
        </div>
      </div>
      <p className="text-slate-500 text-xs font-bold uppercase tracking-widest mb-1">{title}</p>
      <h3 className="text-3xl font-bold text-white mb-1">{value}</h3>
      <p className="text-slate-400 text-[10px] font-medium">{subtext}</p>
    </div>
  );
};

export default function DashboardPage() {
  return (
    <div className="space-y-10">
      {/* Üst Başlık Alanı */}
      <div>
        <h1 className="text-4xl font-bold text-white tracking-tighter">Sağlık Komuta Merkezi</h1>
        <p className="text-slate-400 mt-1 uppercase text-[10px] font-bold tracking-[0.2em]">HealthScope AI Lab v1.0</p>
      </div>

      {/* İstatistik Kartları */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Yapay Zeka Çekirdeği" 
          value="BERTurk-Med" 
          subtext="Tıbbi Dil Modeli Aktif" 
          icon={Brain} 
          color="blue" 
        />
        <StatCard 
          title="Analiz Kapasitesi" 
          value="1M+ Veri" 
          subtext="İşlenmiş Klinik Kayıt" 
          icon={Database} 
          color="purple" 
        />
        <StatCard 
          title="Validasyon (Loss)" 
          value="1.194" 
          subtext="Final Weights Ready" 
          icon={Database} 
          color="purple" 
        />
        <StatCard 
          title="Güven Skoru" 
          value="%91.2" 
          subtext="Doğrulanmış Tahmin Başarısı" 
          icon={Activity} 
          color="emerald" 
        />
        <StatCard 
          title="Altyapı" 
          value="RTX 4060" 
          subtext="GPU Hızlandırma Aktif" 
          icon={Zap} 
          color="amber" 
        />
      </div>

      {/* Tanıtım ve Hızlı Aksiyon Alanı */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-12">
        {/* Vizyon Kartı */}
        <div className="bg-slate-900/20 border border-slate-800/40 p-8 rounded-[2.5rem] flex flex-col justify-center">
          <h2 className="text-2xl font-bold text-blue-400 mb-4 italic">HealthScope Nedir?</h2>
          <p className="text-slate-300 leading-relaxed text-sm">
            HealthScope, karmaşık tıbbi verileri ve kan tahlili sonuçlarını 
            <span className="text-white font-semibold"> BERT tabanlı derin öğrenme </span> 
            mimarisi ile analiz eden bir karar destek sistemidir. 
            Gıda ve Yazılım Mühendisliği disiplinlerini birleştiren sistem, 
            klinik bulgular arasındaki gizli ilişkileri profesyonel düzeyde yorumlar.
          </p>
        </div>

        {/* Aksiyon Kartı */}
        <div className="bg-gradient-to-br from-blue-600/10 to-purple-600/10 border border-blue-500/20 p-8 rounded-[2.5rem] flex items-center justify-between group">
          <div className="max-w-[60%]">
            <h3 className="text-xl font-bold text-white mb-2">Hemen Analize Başla</h3>
            <p className="text-slate-400 text-xs italic">
              Laboratuvar verilerinizi sisteme girin, yapay zeka saniyeler içinde raporlasın.
            </p>
          </div>
          <Link href="/kan-analizi" className="bg-blue-600 hover:bg-blue-500 text-white p-4 rounded-2xl font-bold transition-all transform group-hover:scale-110 active:scale-95 shadow-lg shadow-blue-900/20">
            <ArrowRight size={24} />
          </Link>
        </div>
      </div>

      {/* Alt Bilgi Barı */}
      <div className="pt-10 border-t border-slate-800/40">
        <div className="flex justify-between items-center text-slate-500 text-[10px] font-bold uppercase tracking-widest">
          <span>Sistem Durumu: Çevrimiçi</span>
          <span>GPU Sıcaklığı: 73°C Stable</span>
          <span>Ankara University AI Project</span>
        </div>
      </div>
    </div>
  );
}