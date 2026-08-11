"use client";
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2, ChevronDown, Loader2, Search, Upload, X,
} from "lucide-react";

import { GROUPED_PARAMETERS, PARAMETER_BY_ID, isSexSpecific, referenceText } from "@/lib/catalog";
import { PRESET_CASES, PRESET_DOMAINS, validatePresets, type PresetCase } from "@/lib/presets";
import { uploadReport, type UploadResponse } from "@/lib/api";
import { Badge, Notice, Panel } from "@/components/ui/Primitives";

const MEMORY_KEY = "healthscope_live_memory";

export interface FormState {
  biometrics: { boy: string; kilo: string; yas: string; cinsiyet: string };
  medical: { kronik: string; genetik: string; alerjiler: string[] };
  labValues: Record<string, string>;
}

const EMPTY_FORM: FormState = {
  biometrics: { boy: "", kilo: "", yas: "", cinsiyet: "male" },
  medical: { kronik: "", genetik: "", alerjiler: [] },
  labValues: {},
};

interface AnalysisFormProps {
  onAnalyze: (data: FormState) => void;
  isLoading: boolean;
  disabled?: boolean;
  pdfSupported?: boolean;
}

/** Form içi geçici bildirim (bileşen adı `Notice` ile karışmasın diye ayrı ad). */
type FormNotice = { kind: "success" | "error" | "info"; text: string } | null;

const inputClass =
  "w-full rounded-md border bg-raised px-2.5 py-1.5 text-sm text-ink outline-none transition-colors placeholder:text-ink-subtle focus:border-accent";

export const AnalysisForm = ({
  onAnalyze,
  isLoading,
  disabled = false,
  pdfSupported = true,
}: AnalysisFormProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isPresetsOpen, setIsPresetsOpen] = useState(false);
  const [presetSearch, setPresetSearch] = useState("");
  const [presetDomain, setPresetDomain] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [notice, setNotice] = useState<FormNotice>(null);
  const [ocrFilled, setOcrFilled] = useState<string[]>([]);
  const [suspects, setSuspects] = useState<UploadResponse["suspects"]>([]);
  const [formData, setFormData] = useState<FormState>(EMPTY_FORM);

  const totalParameters = useMemo(
    () => GROUPED_PARAMETERS.reduce((sum, group) => sum + group.parameters.length, 0),
    [],
  );
  const filledCount = useMemo(
    () => Object.values(formData.labValues).filter((value) => value !== "").length,
    [formData.labValues],
  );

  const visiblePresets = useMemo(() => {
    const needle = presetSearch.trim().toLocaleLowerCase("tr");
    return PRESET_CASES.filter((preset) => {
      if (presetDomain && preset.expected?.primary_domain !== presetDomain) return false;
      if (!needle) return true;
      return `${preset.name} ${preset.description} ${preset.medical.kronik} ${preset.expected?.primary_domain ?? ""}`
        .toLocaleLowerCase("tr")
        .includes(needle);
    });
  }, [presetSearch, presetDomain]);

  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      validatePresets().forEach((problem) => console.warn("[HealthScope preset]", problem));
    }
  }, []);

  const persist = (state: FormState) => {
    try {
      localStorage.setItem(MEMORY_KEY, JSON.stringify(state));
    } catch (error) {
      console.error("Hafızaya kaydetme hatası:", error);
    }
  };

  const loadCaseIntoForm = (preset: PresetCase) => {
    const next: FormState = {
      biometrics: { ...preset.biometrics },
      medical: {
        kronik: preset.medical.kronik,
        genetik: preset.medical.genetik,
        alerjiler: [...preset.medical.alerjiler],
      },
      labValues: { ...preset.labValues },
    };
    setFormData(next);
    setOcrFilled([]);
    setSuspects([]);
    persist(next);
    setNotice({ kind: "info", text: `"${preset.name}" forma yüklendi.` });
  };

  const loadMemoryCase = () => {
    const stored = localStorage.getItem(MEMORY_KEY);
    if (!stored) {
      setNotice({ kind: "info", text: "Geçici bellekte kayıtlı veri bulunamadı." });
      return;
    }
    try {
      const parsed = JSON.parse(stored) as Partial<FormState>;
      setFormData({
        biometrics: parsed.biometrics ?? EMPTY_FORM.biometrics,
        medical: parsed.medical ?? EMPTY_FORM.medical,
        labValues: parsed.labValues ?? {},
      });
      setNotice({ kind: "success", text: "Bellekteki son analiz verileri yüklendi." });
    } catch (error) {
      console.error("Hafıza okuma hatası:", error);
      setNotice({ kind: "error", text: "Bellekteki veri bozulmuş, yüklenemedi." });
    }
  };

  const resetForm = () => {
    setFormData(EMPTY_FORM);
    setOcrFilled([]);
    setSuspects([]);
    setNotice({ kind: "info", text: "Form temizlendi." });
  };

  const handleBioChange = (field: keyof FormState["biometrics"], value: string) =>
    setFormData((prev) => ({ ...prev, biometrics: { ...prev.biometrics, [field]: value } }));

  const handleMedicalChange = (field: keyof FormState["medical"], value: string | string[]) =>
    setFormData((prev) => ({ ...prev, medical: { ...prev.medical, [field]: value } }));

  const handleLabChange = (id: string, value: string) => {
    setFormData((prev) => ({ ...prev, labValues: { ...prev.labValues, [id]: value } }));
    setOcrFilled((prev) => prev.filter((key) => key !== id));
    setSuspects((prev) => prev.filter((item) => item.parameter !== id));
  };

  const applySuggestion = (parameterId: string, suggestion: string) => {
    setFormData((prev) => ({ ...prev, labValues: { ...prev.labValues, [parameterId]: suggestion } }));
    setSuspects((prev) => prev.filter((item) => item.parameter !== parameterId));
    setOcrFilled((prev) => prev.filter((key) => key !== parameterId));
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (isPdf && !pdfSupported) {
      setNotice({
        kind: "error",
        text: "Sunucuda PDF desteği kapalı (Poppler bulunamadı). Raporu PNG veya JPG olarak yükleyin.",
      });
      return;
    }

    setIsUploading(true);
    setNotice({ kind: "info", text: `${file.name} okunuyor...` });
    try {
      const data = await uploadReport(file);
      const keys = Object.keys(data.extracted);

      if (keys.length === 0) {
        setNotice({
          kind: "error",
          text: "Rapor okundu ancak tanınan bir tahlil parametresi bulunamadı. Görsel kalitesini artırmayı deneyin.",
        });
        return;
      }

      setFormData((prev) => ({ ...prev, labValues: { ...prev.labValues, ...data.extracted } }));
      setOcrFilled(keys);
      setSuspects(data.suspects ?? []);
      setNotice({
        kind: (data.suspects?.length ?? 0) > 0 ? "error" : "success",
        text: `${data.page_count} sayfa okundu, ${keys.length} parametre dolduruldu. ${data.notice}`,
      });
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Yükleme başarısız." });
    } finally {
      setIsUploading(false);
    }
  };

  const triggerAnalysis = () => {
    persist(formData);
    onAnalyze(formData);
  };

  const biometricsComplete =
    formData.biometrics.boy !== "" && formData.biometrics.kilo !== "" && formData.biometrics.yas !== "";
  const canAnalyze = !isLoading && !disabled && biometricsComplete && filledCount > 0;

  return (
    <div className="space-y-5 pb-16">
      {/* ── VAKA HAVUZU ── */}
      <Panel className="overflow-hidden" >
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
          <button
            type="button"
            onClick={() => setIsPresetsOpen(!isPresetsOpen)}
            aria-expanded={isPresetsOpen}
            className="flex items-center gap-2 text-left"
          >
            <ChevronDown
              size={15}
              className={`text-ink-subtle transition-transform ${isPresetsOpen ? "rotate-180" : ""}`}
            />
            <span>
              <span className="block text-sm font-semibold text-ink">Klinik vaka havuzu</span>
              <span className="block text-[11px] text-ink-subtle">
                {isPresetsOpen
                  ? `${visiblePresets.length} / ${PRESET_CASES.length} vaka gösteriliyor`
                  : `${PRESET_CASES.length} vaka · ${PRESET_DOMAINS.length} sistem`}
              </span>
            </span>
          </button>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={loadMemoryCase}
              className="rounded-md border border-line px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-hover hover:text-ink"
            >
              Son veriyi çek
            </button>
            <button
              type="button"
              onClick={resetForm}
              className="rounded-md border border-line px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-hover hover:text-ink"
            >
              Temizle
            </button>
          </div>
        </div>

        {isPresetsOpen && (
          <div className="border-t border-line bg-sunken">
            <div className="space-y-3 p-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" size={14} />
                <input
                  autoFocus
                  value={presetSearch}
                  onChange={(event) => setPresetSearch(event.target.value)}
                  placeholder="Vaka, sistem veya şikayet ara (anemi, tiroid, ağır)..."
                  className={`${inputClass} border-line pl-9`}
                />
              </div>
              <div className="flex flex-wrap gap-1.5">
                <FilterChip active={presetDomain === null} onClick={() => setPresetDomain(null)}>
                  Tümü ({PRESET_CASES.length})
                </FilterChip>
                {PRESET_DOMAINS.map((domain) => (
                  <FilterChip
                    key={domain}
                    active={presetDomain === domain}
                    onClick={() => setPresetDomain(presetDomain === domain ? null : domain)}
                  >
                    {domain}
                  </FilterChip>
                ))}
              </div>
            </div>

            <div className="max-h-96 overflow-y-auto px-4 pb-4">
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {visiblePresets.map((preset) => (
                  <button
                    key={preset.name}
                    type="button"
                    onClick={() => {
                      loadCaseIntoForm(preset);
                      setIsPresetsOpen(false);
                    }}
                    className="rounded-md border border-line bg-raised p-3 text-left transition-colors hover:border-accent-line hover:bg-accent-soft"
                  >
                    <p className="text-[13px] font-medium text-ink">{preset.name}</p>
                    <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-ink-muted">
                      {preset.description}
                    </p>
                    <p className="mt-2 text-[10px] text-ink-subtle">
                      {preset.biometrics.yas} yaş ·{" "}
                      {preset.biometrics.cinsiyet === "male" ? "Erkek" : "Kadın"}
                      {preset.expected ? ` · ${preset.expected.must_flag.length} sapma` : ""}
                    </p>
                  </button>
                ))}
              </div>
              {visiblePresets.length === 0 && (
                <p className="py-8 text-center text-xs text-ink-subtle">
                  Aramanla eşleşen vaka bulunamadı.
                </p>
              )}
            </div>
          </div>
        )}
      </Panel>

      {/* ── DURUM MESAJI ── */}
      {notice && (
        <Notice
          tone={notice.kind === "success" ? "success" : notice.kind === "error" ? "danger" : "info"}
          action={
            <button
              onClick={() => setNotice(null)}
              aria-label="Kapat"
              className="shrink-0 text-ink-subtle transition-colors hover:text-ink"
            >
              <X size={14} />
            </button>
          }
        >
          {notice.text}
        </Notice>
      )}

      {/* ── ŞÜPHELİ OCR OKUMALARI ──
          Gerçek bir hastane raporunda EasyOCR "2.9" değerini "29" okudu ve
          normal bir sonucu %314 sapma gösteren sahte bulguya çevirdi. */}
      {suspects.length > 0 && (
        <Notice tone="danger" title={`${suspects.length} şüpheli okuma — analiz öncesi doğrulayın`}>
          <div className="mt-2 space-y-2">
            {suspects.map((item) => (
              <div
                key={item.parameter}
                className="flex flex-col gap-2 rounded-md border border-high-line bg-raised px-3 py-2 sm:flex-row sm:items-center"
              >
                <p className="flex-1 text-[12px] leading-relaxed text-ink">{item.message}</p>
                {item.suggestion && (
                  <button
                    type="button"
                    onClick={() => applySuggestion(item.parameter, item.suggestion!)}
                    className="shrink-0 rounded-md bg-high px-3 py-1.5 text-[11px] font-semibold text-white transition-opacity hover:opacity-90"
                  >
                    {item.suggestion} olarak düzelt
                  </button>
                )}
              </div>
            ))}
          </div>
        </Notice>
      )}

      {ocrFilled.length > 0 && suspects.length === 0 && (
        <Notice tone="warn">
          <strong>{ocrFilled.length} alan OCR ile dolduruldu</strong> ve aşağıda sarı işaretlendi.
          Yanlış okuma yanlış çıkarıma yol açar — analizi başlatmadan önce raporunuzla karşılaştırın.
        </Notice>
      )}

      {/* ── OCR YÜKLEME ── */}
      <button
        type="button"
        onClick={() => !isUploading && !disabled && fileInputRef.current?.click()}
        disabled={isUploading || disabled}
        className="flex w-full items-center gap-3 rounded-lg border border-dashed border-line bg-raised px-5 py-4 text-left transition-colors enabled:hover:border-accent-line enabled:hover:bg-accent-soft disabled:opacity-60"
      >
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          accept={pdfSupported ? ".pdf,.png,.jpg,.jpeg" : ".png,.jpg,.jpeg"}
          onChange={handleFileUpload}
          disabled={isUploading || disabled}
        />
        {isUploading ? (
          <Loader2 className="animate-spin text-accent" size={18} />
        ) : (
          <Upload className="text-accent" size={18} />
        )}
        <span>
          <span className="block text-sm font-medium text-ink">
            {isUploading ? "Rapor okunuyor..." : "Tahlil raporu yükle"}
          </span>
          <span className="block text-[11px] text-ink-subtle">
            {pdfSupported ? "PDF (tüm sayfalar), PNG veya JPG" : "PNG veya JPG"} · yerel EasyOCR ile
            işlenir, buluta gönderilmez
          </span>
        </span>
      </button>

      {/* ── HASTA BİLGİLERİ ── */}
      <Panel title="Hasta bilgileri" description="Referans aralıkları cinsiyete göre değişir">
        <div className="grid gap-4 md:grid-cols-4">
          {(
            [
              { field: "boy", label: "Boy (cm)", placeholder: "180" },
              { field: "kilo", label: "Kilo (kg)", placeholder: "75" },
              { field: "yas", label: "Yaş", placeholder: "25" },
            ] as const
          ).map(({ field, label, placeholder }) => (
            <label key={field} className="block">
              <span className="mb-1.5 block text-[11px] font-medium text-ink-muted">{label}</span>
              <input
                type="number"
                placeholder={placeholder}
                value={formData.biometrics[field]}
                onChange={(event) => handleBioChange(field, event.target.value)}
                className={`${inputClass} tnum border-line`}
              />
            </label>
          ))}
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-medium text-ink-muted">Cinsiyet</span>
            <select
              value={formData.biometrics.cinsiyet}
              onChange={(event) => handleBioChange("cinsiyet", event.target.value)}
              className={`${inputClass} cursor-pointer border-line`}
            >
              <option value="male">Erkek</option>
              <option value="female">Kadın</option>
            </select>
          </label>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-medium text-ink-muted">
              Kronik hastalık ve öykü
            </span>
            <textarea
              placeholder="Mevcut hastalıklar (ör. reflü, gut, tiroid)..."
              value={formData.medical.kronik}
              maxLength={500}
              rows={3}
              onChange={(event) => handleMedicalChange("kronik", event.target.value)}
              className={`${inputClass} resize-none border-line`}
            />
            <span className="mt-1 block text-[10px] text-ink-subtle">
              Anahtar kelimeler (reflü, kabızlık, yorgunluk, stres) ek beslenme protokolü tetikler.
            </span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-medium text-ink-muted">Alerjiler</span>
            <textarea
              placeholder="Virgülle ayırın (ör. Yumurta, Ceviz, Süt)..."
              value={formData.medical.alerjiler.join(", ")}
              rows={3}
              onChange={(event) =>
                handleMedicalChange(
                  "alerjiler",
                  event.target.value.split(",").map((item) => item.trim()).filter(Boolean),
                )
              }
              className={`${inputClass} resize-none border-line`}
            />
            <span className="mt-1 block text-[10px] text-ink-subtle">
              Alerjen içeren besinler öneri listesinden çıkarılır.
            </span>
          </label>
        </div>
      </Panel>

      {/* ── LABORATUVAR PANELLERİ (katalogdan üretilir) ── */}
      {GROUPED_PARAMETERS.map((group) => (
        <Panel
          key={group.id}
          title={group.label}
          aside={<Badge>{group.parameters.length} parametre</Badge>}
        >
          <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {group.parameters.map((parameter) => {
              const isOcr = ocrFilled.includes(parameter.id);
              const isSuspect = suspects.some((item) => item.parameter === parameter.id);
              const refLabel = referenceText(parameter, formData.biometrics.cinsiyet);
              return (
                <div key={parameter.id}>
                  <div className="mb-1 flex items-baseline justify-between gap-1">
                    <label
                      htmlFor={`lab-${parameter.id}`}
                      title={parameter.label}
                      className="truncate text-[11px] font-medium text-ink-muted"
                    >
                      {parameter.short}
                    </label>
                    <span
                      className={`tnum shrink-0 text-[10px] ${
                        isSexSpecific(parameter) ? "text-accent" : "text-ink-subtle"
                      }`}
                      title={
                        isSexSpecific(parameter)
                          ? "Referans aralığı cinsiyete göre değişir"
                          : undefined
                      }
                    >
                      {refLabel}
                    </span>
                  </div>
                  <input
                    id={`lab-${parameter.id}`}
                    type="text"
                    inputMode="decimal"
                    placeholder={parameter.unit}
                    value={formData.labValues[parameter.id] ?? ""}
                    onChange={(event) => handleLabChange(parameter.id, event.target.value)}
                    aria-invalid={isSuspect}
                    className={`${inputClass} tnum ${
                      isSuspect
                        ? "border-high bg-high-soft"
                        : isOcr
                          ? "border-warn-line bg-warn-soft"
                          : "border-line"
                    }`}
                  />
                </div>
              );
            })}
          </div>
        </Panel>
      ))}

      {/* ── ANALİZ ── */}
      <div className="sticky bottom-0 -mx-5 border-t border-line bg-raised/95 px-5 py-3 backdrop-blur md:-mx-9 md:px-9">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="tnum text-xs text-ink-muted">
            {filledCount} / {totalParameters} parametre girildi
            <span className="ml-2 text-ink-subtle">
              · {Object.keys(PARAMETER_BY_ID).length} parametrelik katalog
            </span>
          </p>
          <div className="flex items-center gap-3">
            {!canAnalyze && !isLoading && (
              <span className="text-[11px] text-ink-subtle">
                {disabled
                  ? "Sunucu çevrimdışı"
                  : !biometricsComplete
                    ? "Boy, kilo ve yaş gerekli"
                    : "En az bir değer girin"}
              </span>
            )}
            <button
              onClick={triggerAnalysis}
              disabled={!canAnalyze}
              className="inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-colors enabled:hover:bg-accent-hover disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-subtle"
            >
              {isLoading ? (
                <>
                  <Loader2 className="animate-spin" size={16} /> İşleniyor...
                </>
              ) : (
                <>
                  <CheckCircle2 size={16} /> Analizi başlat
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-sm border px-2.5 py-1 text-[11px] font-medium transition-colors ${
        active
          ? "border-accent-line bg-accent-soft text-accent"
          : "border-line bg-raised text-ink-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
