"use client";
import React, { useState } from 'react';
import { AnalysisForm } from '@/components/analysis/AnalysisForm';
import { ResultCard } from '@/components/analysis/ResultCard';



export default function KanAnaliziPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);

  const handleRunAnalysis = async (formData: any) => {
    setIsLoading(true);
    try {
      const response = await fetch('http://127.0.0.1:8000/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          values: formData.labValues,
          biometrics: formData.biometrics,
          medical: formData.medical
        })
      });

      if (!response.ok) throw new Error("Sunucu analizi tamamlayamadı.");

      const data = await response.json();

      
      
      // ── YENİ KURUMSAL BACKEND İLE FRONTEND KARTLARININ KUSURSUZ EŞLEŞMESİ ──
      setAnalysisResult({
        // 1. Ana Karar Metni
        summary: data.executive_summary || "Analiz tamamlandı, bulgular listeleniyor.",
        
        // 2. Biyometrik ve Fizyolojik Veriler (Yaş, Cinsiyet, VKI)
        patient_metrics: {
          age: Number(formData.biometrics.yas) || 0,
          gender: formData.biometrics.cinsiyet === "male" ? "Erkek" : "Kadın",
          bmi: data.physiological_metrics?.bmi || 0,
          allergy_count: Array.isArray(formData.medical.alerjiler) 
            ? formData.medical.alerjiler.length 
            : 0
        },

        // 3. Yapay Zeka Olasılık Grafiği (Olası Teşhisler Çubukları için)
        ai_report: {
          top_diagnosis: data.ai_inference_results?.probabilities_chart_data?.[0]?.diagnosis || "Metabolik Düzensizlik",
          // Backend'den gelen objeyi ResultCard'ın beklediği {name, probability} formatına haritalıyoruz
          probabilities: (data.ai_inference_results?.probabilities_chart_data || []).map((item: any) => ({
            name: item.diagnosis,
            probability: `${item.probability}%`
          })),
          detailed_comment: `İnferans motoru (v${data.engine_version}) tahlil verilerini ${data.clinical_findings?.primary_focus_domain || 'Klinik'} perspektifinden işleyerek ${data.timestamp}ms'de sonuçlandırdı.`
        },

        // 4. Tespit Edilen Sapmalar (Kırmızı Uyarılar Bölümü)
        risks: (data.clinical_findings?.abnormal_parameters_detected || []).map(
          (item: any) => `${item.label} parametresi %${item.deviation_percentage} ${item.status} (${item.value} ${item.unit})`
        ),

        // 5. Gıda Mühendisliği & Beslenme Protokolü
        foods: data.bio_nutritional_protocol?.allergy_cleared_foods || [],
        
        // 6. Biyokimyasal Sinerji ve Beslenme Tavsiyesi
        dietAdvice: (data.bio_nutritional_protocol?.biochemical_synergies || []).join(" ") 
          || "Fizyolojik dengeyi korumak için çeşitli ve dengeli beslenme protokolü önerilir."
      });
      
    } catch (error) {
      console.error("Analiz Hatası:", error);
      alert("API bağlantı veya veri haritalama hatası!");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-8">
      <h1 className="text-4xl font-bold text-white tracking-tighter">AI Derin Analiz Merkezi</h1>

      
      {!analysisResult ? (
        <AnalysisForm onAnalyze={handleRunAnalysis} isLoading={isLoading} />
      ) : (
        <div className="space-y-6 animate-in fade-in zoom-in duration-500">
          <button 
            onClick={() => setAnalysisResult(null)} 
            className="bg-slate-800 text-blue-400 px-6 py-3 rounded-2xl font-bold border border-slate-700 transition-all hover:bg-slate-700"
          >
            ← YENİ ANALİZ BAŞLAT
          </button>
          <ResultCard result={analysisResult} />
        </div>
      )}
    </div>
  );
}