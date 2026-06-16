"use client";
import React, { useRef, useState } from 'react';
import { 
  Upload, Activity, Loader2, Microchip, Scale, 
  Ruler, HeartPulse, ShieldAlert, User, Info,
  Zap, Droplet, Flame // <--- Bu üçünü buraya ekle
} from 'lucide-react';

interface AnalysisFormProps {
  onAnalyze: (data: any) => void;
  isLoading: boolean;
}

// ── 1. HEALTHSCOPE LOKAL KLİNİK VAKA VERİTABANI (PRESETS) ──
// (Veritabanı her zaman bileşenin DIŞINDA, importların altında durmalıdır)
const PRESET_CASES = [
  {
   name: "🍺 İleri Derece Hepatosteatoz & Alkolik Hepatit",
    description: "Ciddi karaciğer parankim hasarı, biliyer stres ve sentetik fonksiyon bozukluğu.",
    biometrics: { boy: "182", kilo: "95", yas: "45", cinsiyet: "male" },
    medical: { kronik: "Alkol Kullanım Bozukluğu", genetik: "", alerjiler: [] },
    labValues: {
      // Hemogram (Makrositoz sıktır)
      wbc: "11.5", rbc: "3.80", hgb: "12.5", hct: "38.0", mcv: "102.4", mch: "33.5", mchc: "34.0", plt: "115", rdw: "16.5",
      neu_perc: "72", neu: "8.2", lym_perc: "18", lym: "2.0", mono_perc: "8", mono: "0.9", eos_perc: "1", eos: "0.1", baso_perc: "1", baso: "0.1",
      // Biyokimya (ALT < AST oranı ve GGT yüksekliği)
      ure: "15", kreatinin: "0.62", ast: "185", alt: "92", ck: "130", alp: "195", urik_asit: "7.8", sodyum: "132", potasyum: "3.2", fosfor: "2.4", kalsiyum: "8.2",
      // Endokrin & Diyabet
      tsh: "1.2", ft4: "0.88", ft3: "2.4", parathormon: "35", ferritin: "550", vit_b12: "190",
      glukoz: "112", hba1c: "5.8", insulin: "22", yassi_epitel: "2", yassi_olmayan_epitel: "0",
      // Lipid & Demir
      total_kolesterol: "245", ldl: "165", hdl: "28", trigliserid: "380", demir: "165", tibc: "180"
    }
  },
  {
    name: "🥩 Gut Artriti & Metabolik Ürisemi",
    description: "Yüksek ürik asit, akut inflamasyon ve metabolik sendrom bileşenleri.",
    biometrics: { boy: "175", kilo: "98", yas: "52", cinsiyet: "male" },
    medical: { kronik: "Gut, Hipertansiyon", genetik: "Ailede ürolitiyazis", alerjiler: [] },
    labValues: {
      wbc: "12.8", rbc: "5.20", hgb: "15.5", hct: "46.5", mcv: "89.5", mch: "30.5", mchc: "33.5", plt: "340", rdw: "12.5",
      neu_perc: "75", neu: "9.6", lym_perc: "15", lym: "1.9", mono_perc: "8", mono: "1.0", eos_perc: "1", eos: "0.1", baso_perc: "1", baso: "0.1",
      ure: "45", kreatinin: "1.15", ast: "32", alt: "38", ck: "110", alp: "88", urik_asit: "10.4", sodyum: "142", potasyum: "4.8", fosfor: "3.9", kalsiyum: "9.6",
      tsh: "2.4", ft4: "1.02", ft3: "3.0", parathormon: "42", ferritin: "210", vit_b12: "350",
      glukoz: "108", hba1c: "5.9", insulin: "18", yassi_epitel: "1", yassi_olmayan_epitel: "1",
      total_kolesterol: "255", ldl: "175", hdl: "38", trigliserid: "240", demir: "95", tibc: "260"
    }
  },
  {
    name: "🥦 Megaloblastik Anemi (Vitamin B12 Eksikliği)",
    description: "Nörolojik semptomlar ve karakteristik makrositer anemi bulguları.",
    biometrics: { boy: "168", kilo: "55", yas: "68", cinsiyet: "female" },
    medical: { kronik: "Atrofik Gastrit", genetik: "", alerjiler: [] },
    labValues: {
      wbc: "3.8", rbc: "2.80", hgb: "8.8", hct: "26.5", mcv: "112.5", mch: "36.5", mchc: "33.0", plt: "125", rdw: "19.5",
      neu_perc: "45", neu: "1.7", lym_perc: "42", lym: "1.6", mono_perc: "10", mono: "0.4", eos_perc: "2", eos: "0.08", baso_perc: "1", baso: "0.02",
      ure: "32", kreatinin: "0.82", ast: "28", alt: "22", ck: "85", alp: "72", urik_asit: "4.2", sodyum: "138", potasyum: "3.8", fosfor: "3.1", kalsiyum: "8.9",
      tsh: "3.1", ft4: "0.85", ft3: "2.6", parathormon: "52", ferritin: "240", vit_b12: "85",
      glukoz: "95", hba1c: "5.5", insulin: "5", yassi_epitel: "3", yassi_olmayan_epitel: "0",
      total_kolesterol: "185", ldl: "110", hdl: "52", trigliserid: "115", demir: "135", tibc: "240"
    }
  },
  {
    name: "🏃‍♂️ Hipertiroidi & Graves Hastalığı",
    description: "Hipermetabolik süreç, düşük TSH ve kardiyak taşikardi eşlikli klinik.",
    biometrics: { boy: "165", kilo: "48", yas: "31", cinsiyet: "female" },
    medical: { kronik: "Çarpıntı", genetik: "Ailede Tiroid Hastalıkları", alerjiler: [] },
    labValues: {
      wbc: "4.8", rbc: "4.60", hgb: "13.8", hct: "41.5", mcv: "89.0", mch: "30.0", mchc: "33.5", plt: "260", rdw: "12.8",
      neu_perc: "58", neu: "2.8", lym_perc: "32", lym: "1.5", mono_perc: "8", mono: "0.4", eos_perc: "1", eos: "0.1", baso_perc: "1", baso: "0.05",
      ure: "24", kreatinin: "0.72", ast: "38", alt: "35", ck: "65", alp: "115", urik_asit: "3.8", sodyum: "140", potasyum: "4.1", fosfor: "3.4", kalsiyum: "9.8",
      tsh: "0.02", ft4: "2.45", ft3: "6.8", parathormon: "25", ferritin: "65", vit_b12: "410",
      glukoz: "105", hba1c: "5.4", insulin: "4", yassi_epitel: "2", yassi_olmayan_epitel: "0",
      total_kolesterol: "145", ldl: "85", hdl: "45", trigliserid: "75", demir: "75", tibc: "290"
    }
  },
  {
    name: "🦴 Hiperparatiroidi & Hiperkalsemi",
    description: "Kalsiyum-Fosfor dengesizliği ve kemik rezorbsiyonu riski.",
    biometrics: { boy: "172", kilo: "70", yas: "58", cinsiyet: "female" },
    medical: { kronik: "Tekrarlayan böbrek taşları", genetik: "", alerjiler: [] },
    labValues: {
      wbc: "7.4", rbc: "4.50", hgb: "13.5", hct: "40.0", mcv: "90.0", mch: "30.0", mchc: "33.5", plt: "210", rdw: "13.0",
      neu_perc: "60", neu: "4.4", lym_perc: "30", lym: "2.2", mono_perc: "8", mono: "0.6", eos_perc: "1", eos: "0.1", baso_perc: "1", baso: "0.07",
      ure: "42", kreatinin: "1.12", ast: "22", alt: "20", ck: "90", alp: "135", urik_asit: "5.8", sodyum: "141", potasyum: "4.2", fosfor: "2.1", kalsiyum: "11.8",
      tsh: "1.8", ft4: "1.05", ft3: "3.2", parathormon: "185", ferritin: "110", vit_b12: "320",
      glukoz: "92", hba1c: "5.2", insulin: "8", yassi_epitel: "4", yassi_olmayan_epitel: "1",
      total_kolesterol: "195", ldl: "125", hdl: "48", trigliserid: "110", demir: "88", tibc: "270"
    }
  },
  {
    name: "🦠 Akut Bakteriyel Enfeksiyon & Lökositoz",
    description: "Ciddi lökositoz, nötrofili ve yüksek CRP ile akut inflamatuar yanıt.",
    biometrics: { boy: "180", kilo: "85", yas: "40", cinsiyet: "male" },
    medical: { kronik: "Yok (Akut Pnömoni Şüphesi)", genetik: "", alerjiler: [] },
    labValues: {
      wbc: "18.5", rbc: "4.80", hgb: "14.2", hct: "42.5", mcv: "89.0", mch: "29.8", mchc: "33.2", plt: "385", rdw: "13.5",
      neu_perc: "85", neu: "15.7", lym_perc: "8", lym: "1.5", mono_perc: "5", mono: "0.9", eos_perc: "1", eos: "0.1", baso_perc: "1", baso: "0.18",
      ure: "48", kreatinin: "1.25", ast: "45", alt: "40", ck: "185", alp: "82", urik_asit: "6.5", sodyum: "135", potasyum: "4.1", fosfor: "3.5", kalsiyum: "8.8",
      tsh: "2.2", ft4: "1.10", ft3: "3.4", parathormon: "38", ferritin: "480", vit_b12: "290",
      glukoz: "145", hba1c: "5.9", insulin: "15", yassi_epitel: "3", yassi_olmayan_epitel: "1",
      total_kolesterol: "175", ldl: "115", hdl: "40", trigliserid: "105", demir: "45", tibc: "215"
    }
  }
];

export const AnalysisForm = ({ onAnalyze, isLoading }: AnalysisFormProps) => {
  // ── 2. HOOK'LAR BİLEŞENİN EN TEPESİNDE (React Kuralları) ──
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isPresetsOpen, setIsPresetsOpen] = useState(false);
  const [formData, setFormData] = useState<any>({
    biometrics: { boy: "", kilo: "", yas: "", cinsiyet: "male" },
    medical: { kronik: "", genetik: "", alerjiler: [] },
    labValues: {}
  });

  // ── 3. LOKAL HAFIZA VE FORMU DOLDURMA FONKSİYONLARI (Bileşenin İÇİNDE olmalı) ──
  const loadCaseIntoForm = (preset: typeof PRESET_CASES[0]) => {
    setFormData({
      biometrics: { ...preset.biometrics },
      medical: { 
        kronik: preset.medical.kronik, 
        genetik: preset.medical.genetik,
        // Alerjiler dizi ise koru, string ise diziye çevir
        alerjiler: Array.isArray(preset.medical.alerjiler) 
          ? preset.medical.alerjiler 
          : typeof preset.medical.alerjiler === 'string' 
            ? (preset.medical.alerjiler as string).split(',').map(s => s.trim()) 
            : []
      },
      labValues: { ...preset.labValues }
    });
    
    console.log(`[HealthScope DB] "${preset.name}" forma başarıyla yüklendi.`);
    
    // Yüklenen veriyi anında belleğe de atalım
    try {
      localStorage.setItem("healthscope_live_memory", JSON.stringify({
        biometrics: preset.biometrics,
        medical: preset.medical,
        labValues: preset.labValues
      }));
    } catch (e) {
      console.error("Hafızaya kaydetme hatası:", e);
    }
  };

  const loadMemoryCase = () => {
    const mem = localStorage.getItem("healthscope_live_memory");
    if (mem) {
      try {
        const parsed = JSON.parse(mem);
        setFormData({
          biometrics: parsed.biometrics || { boy: "", kilo: "", yas: "", cinsiyet: "male" },
          medical: parsed.medical || { kronik: "", genetik: "", alerjiler: [] },
          labValues: parsed.labValues || {}
        });
        alert("Geçici bellekteki son analiz verileri yüklendi.");
      } catch (err) {
        console.error("Hafıza okuma hatası:", err);
        alert("Bellekteki veri bozulmuş.");
      }
    } else {
      alert("Geçici bellekte kayıtlı veri bulunamadı.");
    }
  };

  // ── 4. MEVCUT DEĞİŞİKLİK VE YÜKLEME FONKSİYONLARI ──
  const handleBioChange = (field: string, value: string) => {
    setFormData((prev: any) => ({
      ...prev,
      biometrics: { ...prev.biometrics, [field]: value }
    }));
  };

  const handleMedicalChange = (field: string, value: any) => {
    setFormData((prev: any) => ({
      ...prev,
      medical: { ...prev.medical, [field]: value }
    }));
  };

  const handleLabChange = (id: string, value: string) => {
    setFormData((prev: any) => ({
      ...prev,
      labValues: { ...prev.labValues, [id]: value }
    }));
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    console.log("DOSYA SEÇİLDİ, İŞLEM BAŞLIYOR...");
    const file = e.target.files?.[0];
    if (!file) return;

    const bodyData = new FormData();
    bodyData.append("file", file);

    try {
      const response = await fetch('http://127.0.0.1:8000/upload-report', {
        method: 'POST',
        body: bodyData,
      });

      if (!response.ok) {
        console.error("Sunucu yanıt vermedi! Durum kodu:", response.status);
        return;
      }

      const data = await response.json();
      console.log("GELEN VERİ:", data);
      
      if (data.extracted) {
        setFormData((prev: any) => ({
          ...prev,
          labValues: { ...prev.labValues, ...data.extracted }
        }));
        alert("Başarıyla yüklendi!");
      }
    } catch (error) {
      console.error("Ağ hatası veya bağlantı reddedildi:", error);
    }
  };

  // KAN VERİ SETLERİ
 const hemogramFields = [
    { id: 'wbc', label: 'WBC', unit: 'K/uL', ref: '4.0-10.5' },
    { id: 'rbc', label: 'RBC', unit: 'M/uL', ref: '3.90-5.50' },
    { id: 'hgb', label: 'HGB', unit: 'g/dL', ref: '12-16.8' },
    { id: 'hct', label: 'HCT', unit: '%', ref: '36.2-49.7' },
    { id: 'mcv', label: 'MCV', unit: 'fL', ref: '81.7-99.6' },
    { id: 'mch', label: 'MCH', unit: 'pg', ref: '27.1-33.8' },
    { id: 'mchc', label: 'MCHC', unit: 'g/dL', ref: '32.2-35.1' },
    { id: 'plt', label: 'PLT', unit: 'K/uL', ref: '139-345' },
    { id: 'rdw', label: 'RDW', unit: '%', ref: '11.6-16.0' },
    { id: 'pdw', label: 'PDW', unit: '10(GSD)', ref: '0-99.9' },
    { id: 'pct', label: 'PCT', unit: '%', ref: '0-9.99' },
    { id: 'mpv', label: 'MPV', unit: 'fL', ref: '0-99.9' },
    { id: 'neu_perc', label: 'NEU%', unit: '%', ref: '40-66' },
    { id: 'neu', label: 'NEU#', unit: 'K/uL', ref: '2-7.1' },
    { id: 'lym_perc', label: 'LYM%', unit: '%', ref: '25-46' },
    { id: 'lym', label: 'LYM#', unit: 'K/uL', ref: '0.9-3.4' },
    { id: 'mono_perc', label: 'MONO%', unit: '%', ref: '2-12' },
    { id: 'mono', label: 'MONO#', unit: 'K/uL', ref: '0-1.2' },
    { id: 'eos_perc', label: 'EOS%', unit: '%', ref: '0-7' },
    { id: 'eos', label: 'EOS#', unit: 'K/uL', ref: '0-0.4' },
    { id: 'baso_perc', label: 'BASO%', unit: '%', ref: '0-2.5' },
    { id: 'baso', label: 'BASO#', unit: 'K/uL', ref: '0-0.1' },
  ];

  const biochemistryFields = [
    { id: 'ure', label: 'ÜRE', unit: 'mg/dL', ref: '17-43' },
    { id: 'kreatinin', label: 'KREATİNİN', unit: 'mg/dL', ref: '0.66-1.09' },
    { id: 'ast', label: 'AST', unit: 'U/L', ref: '1-35' },
    { id: 'alt', label: 'ALT', unit: 'U/L', ref: '1-35' },
    { id: 'ck', label: 'CK (KİNAZ)', unit: 'U/L', ref: '26-140' },
    { id: 'alp', label: 'ALKALEN FOSFATAZ', unit: 'U/L', ref: '33-98' },
    { id: 'urik_asit', label: 'ÜRİK ASİT', unit: 'mg/dL', ref: '2.6-6.0' },
    { id: 'sodyum', label: 'SODYUM', unit: 'mmol/L', ref: '136-145' },
    { id: 'potasyum', label: 'POTASYUM', unit: 'mmol/L', ref: '3.5-5.1' },
    { id: 'fosfor', label: 'FOSFOR', unit: 'mg/dL', ref: '2.5-4.5' },
    { id: 'kalsiyum', label: 'KALSİYUM', unit: 'mg/dL', ref: '8.5-10.5' },
  ];

  const endocrineFields = [
    { id: 'tsh', label: 'TSH', unit: 'mIU/L', ref: '0.38-5.33' },
    { id: 'ft4', label: 'FREE T4', unit: 'ng/dL', ref: '0.61-1.12' },
    { id: 'ft3', label: 'FREE T3', unit: 'ng/L', ref: '2.6-4.37' },
    { id: 'parathormon', label: 'PARATHORMON', unit: 'ng/L', ref: '12-88' },
    { id: 'ferritin', label: 'FERRİTİN', unit: 'ug/L', ref: '11-306.8' },
    { id: 'vit_b12', label: 'VİTAMİN B12', unit: 'ng/L', ref: '145-914' },
  ];

  const diabetesAndUrineFields = [
    { id: 'glukoz', label: 'GLUKOZ', unit: 'mg/dL', ref: '70-99' },
    { id: 'hba1c', label: 'HbA1C', unit: '%', ref: '3.5-5.6' },
    { id: 'insulin', label: 'İNSÜLİN', unit: 'IU/L', ref: '1.9-23' },
    { id: 'yassi_epitel', label: 'YASSI EPİTEL', unit: 'HPF', ref: '< 5' },
    { id: 'yassi_olmayan_epitel', label: 'YASSI OLMAYAN EPİTEL', unit: 'HPF', ref: '0' },
  ];

  const lipidFields = [
    { id: 'total_kolesterol', label: 'TOTAL KOLESTEROL', unit: 'mg/dL', ref: '1-199' },
    { id: 'ldl', label: 'LDL KOLESTEROL', unit: 'mg/dL', ref: '0-130' },
    { id: 'hdl', label: 'HDL KOLESTEROL', unit: 'mg/dL', ref: '40-90' },
    { id: 'trigliserid', label: 'TRİGLİSERİD', unit: 'mg/dL', ref: '1-200' },
    { id: 'demir', label: 'DEMİR', unit: 'ug/dL', ref: '37-145' },
    { id: 'tibc', label: 'DEMİR BAĞLAMA', unit: 'ug/dL', ref: '118-318' },
  ];
  // Form gönderilirken anlık veriyi hafızaya alalım
  const triggerAnalysis = () => {
    try {
      localStorage.setItem("healthscope_live_memory", JSON.stringify(formData));
    } catch (e) {
      console.error(e);
    }
    onAnalyze(formData);
  };

  return (
    <div className="space-y-8 pb-20">
      
      {/* ── YENİ AKORDEON (AÇILIR/KAPANIR) VAKA HAVUZU PANELİ (En Üstte) ── */}
      <div className="bg-slate-900/40 border border-slate-800/80 rounded-[1.5rem] backdrop-blur-md transition-all duration-500 overflow-hidden select-none">
        
        {/* TIKLANABİLİR BAŞLIK KISMI */}
        <div 
          onClick={() => setIsPresetsOpen(!isPresetsOpen)}
          className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 cursor-pointer hover:bg-slate-800/20 transition-colors"
        >
          <div className="flex items-center gap-3">
            {/* Açılıp kapanmaya göre dönen ok (Chevron) animasyonu */}
            <div className={`w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center text-slate-400 transition-transform duration-300 ${isPresetsOpen ? 'rotate-180' : ''}`}>
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            <div>
              <span className="text-xs font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                Klinik Vaka Havuzu & Otomatik Bellek
              </span>
              <p className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">
                {isPresetsOpen 
                  ? "Paneli daraltmak için tıklayın." 
                  : "Önceden hazırlanmış 16 farklı klinik profili görmek için tıklayın."}
              </p>
            </div>
          </div>
          
          {/* HAFIZADAKİ VERİYİ ÇEK BUTONU (stopPropagation eklendi) */}
          <button 
            onClick={(e) => {
              e.stopPropagation();
              loadMemoryCase();
            }}
            type="button"
            className="self-start md:self-auto text-xs bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 px-3 py-2 rounded-xl font-semibold transition-all flex items-center gap-1.5 z-10"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" /></svg>
            Hafızadaki Son Veriyi Çek
          </button>
        </div>

        {/* İÇERİK KISMI (Sadece isPresetsOpen true olduğunda açılır) */}
        <div className={`transition-all duration-500 ease-in-out ${isPresetsOpen ? 'max-h-[2500px] opacity-100 border-t border-slate-800/50' : 'max-h-0 opacity-0'}`}>
          <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 bg-slate-900/20">
            {PRESET_CASES.map((preset, idx) => (
              <div 
                key={idx}
                onClick={() => {
                  loadCaseIntoForm(preset);
                  setIsPresetsOpen(false); // Herhangi bir vakaya tıklandığında paneli otomatik kapatır
                }}
                className="bg-slate-800/40 hover:bg-slate-800/80 border border-slate-700/50 hover:border-blue-500/40 p-3 rounded-xl cursor-pointer transition-all group flex flex-col justify-between"
              >
                <div>
                  <h4 className="text-xs font-bold text-slate-200 group-hover:text-blue-400 transition-colors line-clamp-1">
                    {preset.name}
                  </h4>
                  <p className="text-[10px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                    {preset.description}
                  </p>
                </div>
                <span className="text-[9px] font-bold text-slate-500 group-hover:text-slate-400 mt-2 block text-right">
                  Forma Yükle →
                </span>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* 1. BÖLÜM: BİYOMETRİK VERİLER */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] p-8 backdrop-blur-md">
        <div className="flex items-center space-x-3 mb-6">
          <User className="text-blue-400" size={24} />
          <h3 className="text-lg font-bold text-white uppercase tracking-widest">Biyometrik Profil</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-2"><Ruler size={12}/> Boy (cm)</label>
            <input 
              type="number" placeholder="180" 
              value={formData.biometrics.boy || ''}
              className="w-full bg-black/40 border border-slate-800 rounded-2xl p-4 text-white outline-none focus:border-blue-500" 
              onChange={(e) => handleBioChange('boy', e.target.value)} 
            />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase flex items-center gap-2"><Scale size={12}/> Kilo (kg)</label>
            <input 
              type="number" placeholder="75" 
              value={formData.biometrics.kilo || ''}
              className="w-full bg-black/40 border border-slate-800 rounded-2xl p-4 text-white outline-none focus:border-blue-500" 
              onChange={(e) => handleBioChange('kilo', e.target.value)} 
            />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Yaş</label>
            <input 
              type="number" placeholder="25" 
              value={formData.biometrics.yas || ''}
              className="w-full bg-black/40 border border-slate-800 rounded-2xl p-4 text-white outline-none focus:border-blue-500" 
              onChange={(e) => handleBioChange('yas', e.target.value)} 
            />
          </div>
          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase">Cinsiyet</label>
            <select 
              value={formData.biometrics.cinsiyet || 'male'}
              className="w-full bg-black/40 border border-slate-800 rounded-2xl p-4 text-white outline-none appearance-none cursor-pointer" 
              onChange={(e) => handleBioChange('cinsiyet', e.target.value)}
            >
              <option value="male">Erkek</option>
              <option value="female">Kadın</option>
            </select>
          </div>
        </div>
      </div>

      {/* 2. BÖLÜM: SAĞLIK GEÇMİŞİ & ALERJİLER */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] p-8 backdrop-blur-md">
          <div className="flex items-center space-x-3 mb-6">
            <HeartPulse className="text-rose-500" size={24} />
            <h3 className="text-lg font-bold text-white uppercase tracking-widest">Kronik & Genetik</h3>
          </div>
          <textarea 
            placeholder="Mevcut hastalıklar ve ailevi geçmişiniz..." 
            value={formData.medical.kronik || ''}
            className="w-full h-32 bg-black/40 border border-slate-800 rounded-2xl p-4 text-white outline-none focus:border-rose-500 resize-none"
            onChange={(e) => handleMedicalChange('kronik', e.target.value)}
          />
        </div>
        <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] p-8 backdrop-blur-md">
          <div className="flex items-center space-x-3 mb-6">
            <ShieldAlert className="text-amber-500" size={24} />
            <h3 className="text-lg font-bold text-white uppercase tracking-widest">Alerjiler</h3>
          </div>
          <textarea 
            placeholder="Gıda veya ilaç alerjilerinizi belirtin (Örn: Gluten, Penisilin)..." 
            value={Array.isArray(formData.medical.alerjiler) ? formData.medical.alerjiler.join(', ') : ''}
            className="w-full h-32 bg-black/40 border border-slate-800 rounded-2xl p-4 text-white outline-none focus:border-amber-500 resize-none"
            onChange={(e) => handleMedicalChange('alerjiler', e.target.value.split(",").map((s: string) => s.trim()))}
          />
        </div>
      </div>

      {/* ── KATEGORİ 1: HEMOGRAM (TAM KAN SAYIMI) ── */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] overflow-hidden backdrop-blur-md">
        <div className="p-5 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
          <div className="flex items-center space-x-3 text-red-400"><Activity size={20} /><h3 className="text-sm font-bold text-white uppercase tracking-widest">Hemogram (Tam Kan Sayımı)</h3></div>
          <span className="text-xs bg-red-500/10 text-red-400 px-2.5 py-1 rounded-full font-mono">22 Parametre</span>
        </div>
        <div className="p-8 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
          {hemogramFields.map(field => (
            <div key={field.id} className="space-y-2 group">
              <div className="flex justify-between px-1"><label className="text-[10px] font-bold text-slate-500 group-hover:text-red-400 transition-colors uppercase">{field.label}</label><span className="text-[9px] text-slate-600 italic">{field.ref}</span></div>
              <input type="text" placeholder={field.unit} value={formData.labValues[field.id] || ''} className="w-full bg-black/40 border border-slate-800 rounded-2xl p-3 text-sm text-white focus:border-red-500 outline-none" onChange={(e) => handleLabChange(field.id, e.target.value)} />
            </div>
          ))}
        </div>
      </div>

      {/* ── KATEGORİ 2: BİYOKİMYA & ELEKTROLİTLER ── */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] overflow-hidden backdrop-blur-md">
        <div className="p-5 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
          <div className="flex items-center space-x-3 text-emerald-400"><Zap size={20} /><h3 className="text-sm font-bold text-white uppercase tracking-widest">Biyokimya & Elektrolit Paneli</h3></div>
          <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2.5 py-1 rounded-full font-mono">11 Parametre</span>
        </div>
        <div className="p-8 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-6">
          {biochemistryFields.map(field => (
            <div key={field.id} className="space-y-2 group">
              <div className="flex justify-between px-1"><label className="text-[10px] font-bold text-slate-500 group-hover:text-emerald-400 transition-colors uppercase">{field.label}</label><span className="text-[9px] text-slate-600 italic">{field.ref}</span></div>
              <input type="text" placeholder={field.unit} value={formData.labValues[field.id] || ''} className="w-full bg-black/40 border border-slate-800 rounded-2xl p-3 text-sm text-white focus:border-emerald-500 outline-none" onChange={(e) => handleLabChange(field.id, e.target.value)} />
            </div>
          ))}
        </div>
      </div>

      {/* ── KATEGORİ 3: TİROİD & HORMONLAR ── */}
      <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] overflow-hidden backdrop-blur-md">
        <div className="p-5 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
          <div className="flex items-center space-x-3 text-purple-400"><HeartPulse size={20} /><h3 className="text-sm font-bold text-white uppercase tracking-widest">Tiroid & Hormon Paneli</h3></div>
          <span className="text-xs bg-purple-500/10 text-purple-400 px-2.5 py-1 rounded-full font-mono">6 Parametre</span>
        </div>
        <div className="p-8 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6">
          {endocrineFields.map(field => (
            <div key={field.id} className="space-y-2 group">
              <div className="flex justify-between px-1"><label className="text-[10px] font-bold text-slate-500 group-hover:text-purple-400 transition-colors uppercase">{field.label}</label><span className="text-[9px] text-slate-600 italic">{field.ref}</span></div>
              <input type="text" placeholder={field.unit} value={formData.labValues[field.id] || ''} className="w-full bg-black/40 border border-slate-800 rounded-2xl p-3 text-sm text-white focus:border-purple-500 outline-none" onChange={(e) => handleLabChange(field.id, e.target.value)} />
            </div>
          ))}
        </div>
      </div>

      {/* ── KATEGORİ 4 & 5: DİYABET, İDRAR VE LİPİD KOMBOSİ ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* DİYABET & İDRAR */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] overflow-hidden backdrop-blur-md flex flex-col justify-between">
          <div className="p-5 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
            <div className="flex items-center space-x-3 text-amber-400"><Droplet size={20} /><h3 className="text-sm font-bold text-white uppercase tracking-widest">Diyabet & İdrar Mikroskopisi</h3></div>
            <span className="text-xs bg-amber-500/10 text-amber-400 px-2.5 py-1 rounded-full font-mono">5 Parametre</span>
          </div>
          <div className="p-8 grid grid-cols-2 md:grid-cols-3 gap-6 flex-grow">
            {diabetesAndUrineFields.map(field => (
              <div key={field.id} className="space-y-2 group">
                <div className="flex justify-between px-1"><label className="text-[10px] font-bold text-slate-500 group-hover:text-amber-400 transition-colors uppercase">{field.label}</label><span className="text-[9px] text-slate-600 italic">{field.ref}</span></div>
                <input type="text" placeholder={field.unit} value={formData.labValues[field.id] || ''} className="w-full bg-black/40 border border-slate-800 rounded-2xl p-3 text-sm text-white focus:border-amber-500 outline-none" onChange={(e) => handleLabChange(field.id, e.target.value)} />
              </div>
            ))}
          </div>
        </div>

        {/* LİPİD & DEMİR PANELİ */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-[2.5rem] overflow-hidden backdrop-blur-md flex flex-col justify-between">
          <div className="p-5 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
            <div className="flex items-center space-x-3 text-cyan-400"><Flame size={20} /><h3 className="text-sm font-bold text-white uppercase tracking-widest">Lipid & Demir Paneli</h3></div>
            <span className="text-xs bg-cyan-500/10 text-cyan-400 px-2.5 py-1 rounded-full font-mono">6 Parametre</span>
          </div>
          <div className="p-8 grid grid-cols-2 md:grid-cols-3 gap-6 flex-grow">
            {lipidFields.map(field => (
              <div key={field.id} className="space-y-2 group">
                <div className="flex justify-between px-1"><label className="text-[10px] font-bold text-slate-500 group-hover:text-cyan-400 transition-colors uppercase">{field.label}</label><span className="text-[9px] text-slate-600 italic">{field.ref}</span></div>
                <input type="text" placeholder={field.unit} value={formData.labValues[field.id] || ''} className="w-full bg-black/40 border border-slate-800 rounded-2xl p-3 text-sm text-white focus:border-cyan-500 outline-none" onChange={(e) => handleLabChange(field.id, e.target.value)} />
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* 3. BÖLÜM: CLOUD VISION OCR YÜKLEME (Aşağıya Taşındı) */}
      <section className="relative group my-8">
        <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-cyan-500 rounded-[2.5rem] blur opacity-25 group-hover:opacity-50 transition duration-1000"></div>
        <div 
          onClick={() => fileInputRef.current?.click()}
          className="relative bg-slate-900 border border-slate-800 rounded-[2.5rem] p-12 text-center cursor-pointer hover:bg-slate-900/50 transition-all"
        >
          <input type="file" ref={fileInputRef} className="hidden" accept=".pdf,image/*" onChange={handleFileUpload} />
          <Upload className="mx-auto text-blue-500 mb-4" size={32} />
          <h2 className="text-xl font-bold text-white tracking-tight">Tahlil Raporu Yükle (Vision AI)</h2>
          <p className="text-slate-400 mt-2 text-sm font-mono tracking-tighter">Google Cloud Vision ile veriler otomatik işlenecektir.</p>
        </div>
      </section>

      {/* ANALİZ BUTONU */}
      <button 
        onClick={triggerAnalysis}
        disabled={isLoading}
        className="w-full h-24 bg-blue-600 rounded-[2.5rem] shadow-2xl shadow-blue-600/20 active:scale-[0.98] transition-all flex items-center justify-center space-x-6"
      >
        {isLoading ? (
          <div className="flex items-center space-x-3 uppercase font-black tracking-[0.3em] text-white">
             <Loader2 className="animate-spin" size={32} />
             <span>Hücresel Veri İşleniyor...</span>
          </div>
        ) : (
          <>
            <Microchip className="text-white/80" size={32} />
            <span className="text-2xl font-black text-white uppercase tracking-[0.2em]">Kapsamlı AI Analizi Başlat</span>
          </>
        )}
      </button>

    </div>
  );
};