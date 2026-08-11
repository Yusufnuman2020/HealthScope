"use client";
import React from "react";

import type { OrganId } from "@/lib/anatomy";

/**
 * Anatomik şema — önden görünüm (anterior), katmanlı çizim.
 *
 * Katman sırası: gövde → derin iskelet (omurga, klavikula, kol kemikleri) →
 * toplardamar → atardamar → organlar → KABURGA KAFESİ → iç ayrıntılar →
 * bacak kemikleri.
 *
 * Kaburgaların organlardan SONRA çizilmesi kasıtlı: önden bakışta kaburgalar
 * göğüs organlarının önündedir. Önce çizilirse akciğer ve kalp onları tamamen
 * örtüyor ve kafes hiç okunmuyordu — yarı saydam üst katman anatomi atlası
 * görünümünü veriyor.
 *
 * Renk bilgi taşımaz, ŞİDDET taşır: her organ `fillOf()` ile gelen tek renk
 * skalasıyla boyanır. Anatomik doğruluk biçimden okunur — lob yapıları,
 * fissürler, kolon çerçevesi, damar dallanması hep çizimde.
 *
 * ÖNEMLİ — yönelim: önden bakışta izleyicinin SOLU hastanın SAĞIdır.
 * Karaciğer, safra kesesi, çekum ve çıkan kolon solda; mide, dalak, inen kolon
 * ve kalbin apeksi sağda. Sağ akciğer 3 loblu, sol akciğer 2 loblu ve kardiyak
 * çentikli. Sağ böbrek karaciğer nedeniyle soldan bir miktar aşağıdadır.
 *
 * Tüm yollar elle yazıldı; hazır model, stok görsel ya da lisanslı çizim yok.
 */

export interface AnatomyFigureProps {
  /** Organ kimliği → şiddet rengi. */
  fillOf: (id: OrganId) => string;
  isSelected: (id: OrganId) => boolean;
  onSelect: (id: OrganId) => void;
  /** Damar yatağında bulgu var mı — atardamarların rengini belirler. */
  vesselAffected: boolean;
}

const STROKE = "var(--organ-stroke)";
const BONE = "var(--organ-bone)";
const BONE_EDGE = "var(--organ-bone-edge)";
const ARTERY = "var(--organ-vessel)";
const VEIN = "var(--organ-vein)";

/** Sağ taraf yolunu x ekseninde aynalar (orta hat x = 170). */
const MIRROR = "translate(340, 0) scale(-1, 1)";

/**
 * Kaburga geometrisi. Altı çift yeterli: yedincide kafes yay yığınına dönüşüp
 * arkasındaki akciğer ve kalbi okunmaz hâle getiriyordu.
 */
const RIBS = Array.from({ length: 6 }, (_, i) => {
  const y0 = 136 + i * 14;
  const w = 40 + i * 6.6;
  const y1 = y0 + 15 + i * 3.6;
  return {
    left: `M164 ${y0} C ${164 - w} ${y0 + 2}, ${164 - w} ${y1 - 5}, 160 ${y1}`,
    right: `M176 ${y0} C ${176 + w} ${y0 + 2}, ${176 + w} ${y1 - 5}, 180 ${y1}`,
  };
});

/**
 * Şema 20'den fazla organ çiziyor; her birine renk/seçim/tıklama üçlüsünü tek
 * tek geçirmek yerine bağlam üzerinden dağıtılıyor. Bileşen modül seviyesinde
 * tanımlı — render içinde tanımlansaydı her çizimde ağaç yeniden bağlanırdı.
 */
const FigureContext = React.createContext<AnatomyFigureProps | null>(null);

/**
 * Tıklanabilir organ.
 *
 * Çizgi/boya ayrımı: kolon ve ince bağırsak dolgu değil kalın çizgi olarak
 * çizilir — tübüler organlarda kontur takibi yerine şerit çok daha okunaklı.
 */
function Organ({
  id,
  label,
  d,
  line,
  animate,
  transform,
}: {
  id: OrganId;
  label: string;
  d: string;
  /** Verilirse organ dolgu yerine bu kalınlıkta çizgi olarak çizilir. */
  line?: number;
  animate?: "filter";
  transform?: string;
}) {
  const ctx = React.useContext(FigureContext);
  if (!ctx) return null;

  const color = ctx.fillOf(id);
  const cls = ["anatomy-organ", animate === "filter" ? "anatomy-filter" : "", ctx.isSelected(id) ? "is-selected" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <g
      className={cls}
      transform={transform}
      fill={line ? "none" : color}
      // evenodd: pelviste pelvik giriş ve obturator delikleri boşluk kalsın.
      fillRule="evenodd"
      stroke={line ? color : STROKE}
      strokeWidth={line ?? 1}
      strokeLinejoin="round"
      strokeLinecap="round"
      onClick={() => ctx.onSelect(id)}
      role="button"
      tabIndex={0}
      aria-label={label}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          ctx.onSelect(id);
        }
      }}
    >
      <title>{label}</title>
      <path d={d} />
    </g>
  );
}

export function AnatomyFigure(props: AnatomyFigureProps) {
  const { fillOf, onSelect, vesselAffected } = props;
  const vessel = vesselAffected ? fillOf("damar") : ARTERY;

  return (
    <FigureContext.Provider value={props}>
      <svg
        viewBox="0 0 340 700"
        className="anatomy-svg w-full max-w-[320px]"
        role="img"
        aria-label="Bulguların organ sistemlerine dağılımını gösteren anatomik şema"
      >
        <defs>
          <linearGradient id="an-body" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--organ-body)" />
            <stop offset="42%" stopColor="var(--organ-body-light)" />
            <stop offset="100%" stopColor="var(--organ-body)" />
          </linearGradient>
        </defs>

        {/* ══════════ 1. GÖVDE SİLUETİ ══════════ */}
        <g fill="url(#an-body)" stroke={STROKE} strokeWidth="1" strokeLinejoin="round">
          {/* Kollar ve bacaklar — deltoid, dirsek, el / uyluk, diz, baldır, ayak.
              Gövdeden ayrı çizilir; omuzda hafif bindirme, belde açıklık kalır. */}
          <g opacity="0.75">
            {[undefined, MIRROR].map((t, i) => (
              <path
                key={`arm-${i}`}
                transform={t}
                d="M116 114C99 119 87 133 82 154C77 176 72 202 69 230
                   C66 256 63 280 61 302C60 316 59 328 59 338
                   C58 353 65 368 76 368C88 368 94 357 92 340
                   C91 328 89 318 88 302C90 278 94 254 97 230
                   C100 204 105 176 110 155C113 141 117 127 121 119Z"
              />
            ))}
            {[undefined, MIRROR].map((t, i) => (
              <path
                key={`leg-${i}`}
                transform={t}
                d="M100 464C97 490 95 512 95 534C95 552 98 566 101 580
                   C103 596 101 608 102 622C103 638 105 650 106 656
                   C107 664 112 668 122 668C134 668 140 664 139 654
                   C138 640 135 626 134 610C133 592 135 578 138 562
                   C141 542 146 520 150 496C153 480 155 470 156 464Z"
              />
            ))}
          </g>

          {/* Boyun ÖNCE, baş sonra: elips boynun üst kenar çizgisini örtsün.
              Baş 7,5 boy-oranını tutturacak büyüklükte — daha küçüğünde gövde
              şişkin görünüyordu. */}
          <path d="M155 72c1 12 0 22-4 32h38c-4-10-5-20-4-32z" />
          <ellipse cx="170" cy="46" rx="35" ry="42" />
          {/* Ayaklar */}
          {[undefined, MIRROR].map((t, i) => (
            <ellipse key={`foot-${i}`} transform={t} cx="121" cy="665" rx="20" ry="10" opacity="0.75" />
          ))}
          <path
            d="M170 104C150 104 131 108 117 118C104 128 96 146 92 168
               C88 192 87 218 88 244C89 268 92 292 96 312
               C99 330 101 346 100 362C99 382 95 404 94 424
               C94 442 97 456 102 464L238 464C243 456 246 442 246 424
               C246 404 242 382 241 362C240 346 241 330 244 312
               C248 292 251 268 252 244C253 218 252 192 248 168
               C244 146 236 128 223 118C209 108 190 104 170 104Z"
          />
        </g>

        {/* ══════════ 1b. KAS KATMANI ══════════
            Şemanın en kritik parçası. Bu katman olmadan gövde "içi boş bir
            siluetin içinde havada duran organlar" gibi görünüyordu — biçimi
            veren şey organlar değil, çevrelerindeki kas kütlesi.

            Kaslar ÇEVREDE durur, merkez açık bırakılır: anatomi atlaslarındaki
            diseksiyon mantığı budur — ön karın duvarı ve göğüs ortası kaldırılıp
            iç organlar açığa çıkarılır, uzuvlar ve yanlar kaslı kalır. */}
        <g
          fill="var(--organ-muscle)"
          stroke="var(--organ-muscle-edge)"
          strokeWidth="0.9"
          strokeLinejoin="round"
          pointerEvents="none"
        >
          {[undefined, MIRROR].map((t, i) => (
            <g key={i} transform={t}>
              {/* Sternokleidomastoid — boynun karakteristik kayışı */}
              <path d="M152 84C148 92 146 100 148 108L159 110C158 100 159 92 161 85C158 82 154 81 152 84Z" />
              {/* Deltoid — omuz başlığı; figürün omuz genişliğini bu verir */}
              <path d="M121 114C106 119 95 132 90 150C87 161 86 173 88 183C97 185 105 179 110 168C114 157 118 137 124 125C126 119 125 113 121 114Z" />
              {/* Pektoralis major — yelpaze; ortası açık, laterali kaslı */}
              <path d="M141 124C128 124 115 128 107 136C100 143 98 151 100 159C109 163 119 161 127 155C133 150 137 141 140 133C142 128 144 124 141 124Z" />
              {/* Serratus anterior — kaburgalar üzerindeki parmak benzeri dilimler */}
              <path d="M101 170L113 175L108 183ZM99 187L111 192L106 200ZM98 204L110 209L105 217Z" />
              {/* Biceps / brakialis */}
              <path d="M88 178C83 194 79 214 77 232C76 244 79 252 85 253C91 254 94 248 95 238C97 218 99 196 102 180C98 174 92 173 88 178Z" />
              {/* Ön kol kas kütlesi */}
              <path d="M79 262C75 282 72 302 70 320C69 332 72 340 78 340C84 340 87 334 87 324C88 306 91 284 94 264C89 259 83 258 79 262Z" />
              {/* Eksternal oblik — yan karın duvarı; beli o daraltır */}
              <path d="M102 168C96 186 94 210 95 234C96 258 100 282 106 300C112 316 119 326 127 330C131 326 131 316 127 306C119 286 113 262 111 236C109 210 109 186 111 170C108 166 105 165 102 168Z" />
              {/* Gastroknemius — baldır */}
              <path d="M112 590C106 598 103 610 104 622C105 634 109 642 115 643C121 644 125 638 125 628C126 616 124 602 121 592C118 588 115 587 112 590Z" />
            </g>
          ))}
        </g>

        {/* ══════════ 2. DERİN İSKELET ══════════ */}
        <g fill={BONE} stroke={BONE_EDGE} strokeWidth="0.8" strokeLinejoin="round" opacity="0.85">
          {/* Klavikula */}
          <path d="M124 122c14-4 30-6 46-6s32 2 46 6c3 1 3 6 0 7-15 4-30 6-46 6s-31-2-46-6c-3-1-3-6 0-7z" />
          {/* Omurga — servikalden sakruma */}
          <path d="M163 104h14v296h-14z" opacity="0.9" />
          {/* Humerus + ön kol */}
          {[undefined, MIRROR].map((t, i) => (
            <g key={i} transform={t} opacity="0.75">
              {/* Humerus */}
              <path d="M107 134C99 148 93 168 89 190C86 206 84 220 82 232L92 232C94 219 96 205 99 190C103 168 108 149 114 140Z" />
              {/* Radius + ulna */}
              <path d="M81 244C79 260 76 278 75 294C74 306 73 316 73 324L82 324C82 315 83 305 84 294C86 277 88 259 90 244Z" />
            </g>
          ))}
        </g>

        {/* Vertebra aralıkları */}
        <g stroke={BONE_EDGE} strokeWidth="0.7" opacity="0.5">
          {Array.from({ length: 19 }, (_, i) => (
            <line key={i} x1="163" y1={114 + i * 15} x2="177" y2={114 + i * 15} />
          ))}
        </g>

        {/* ══════════ 3. TOPLARDAMARLAR ══════════ */}
        <g fill="none" stroke={VEIN} strokeWidth="2.4" strokeLinecap="round" opacity="0.5">
          {/* Juguler → brakiyosefalik */}
          <path d="M158 82C157 96 156 106 154 114C148 122 134 128 116 138" />
          <path d="M182 82C183 96 184 106 186 114C192 122 206 128 224 138" />
          {/* Kol venleri */}
          <path d="M116 138C108 176 98 224 90 266" strokeWidth="1.9" />
          <path d="M224 138C232 176 242 224 250 266" strokeWidth="1.9" />
          {/* Vena kava süperior + inferior */}
          <path d="M160 148C159 172 158 196 158 214" strokeWidth="3.2" />
          <path d="M162 250C161 300 160 356 161 424" strokeWidth="3.2" />
          {/* Portal ven — bağırsaktan karaciğere */}
          <path d="M170 332C160 324 152 316 150 306" strokeWidth="1.8" />
          {/* İliak → femoral venler */}
          <path d="M161 424L132 468M161 424L208 468" strokeWidth="2.4" />
          <path d="M132 468C128 512 124 560 122 622" strokeWidth="1.9" />
          <path d="M208 468C212 512 216 560 218 622" strokeWidth="1.9" />
        </g>

        {/* ══════════ 4. ATARDAMARLAR ══════════ */}
        <g
          fill="none"
          stroke={vessel}
          strokeWidth="2.4"
          strokeLinecap="round"
          opacity="0.72"
          className="anatomy-organ"
          onClick={() => onSelect("damar")}
          role="button"
          tabIndex={0}
          aria-label="Damar yatağı"
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              onSelect("damar");
            }
          }}
        >
          <title>Damar yatağı</title>
          {/* Karotisler */}
          <path d="M164 82L163 112" />
          <path d="M176 82L177 112" />
          {/* Subklavyen → brakiyal → radial/ulnar */}
          <path d="M163 116C148 122 128 130 110 142" />
          <path d="M177 116C192 122 212 130 230 142" />
          <path d="M110 142C102 178 92 224 84 264" strokeWidth="1.9" />
          <path d="M230 142C238 178 248 224 256 264" strokeWidth="1.9" />
          {/* Arkus aorta ve inen aorta */}
          <path d="M183 178C181 158 186 145 197 143C208 142 214 152 214 164" strokeWidth="3.2" />
          <path d="M176 190C175 244 173 310 173 424" strokeWidth="3.4" />
          {/* Renal arterler, çölyak trunkus, süperior mezenterik — üst karınla
              birlikte kaydırılır ki organlarının hilusuna denk gelsin. */}
          <g transform="translate(0, -42)">
            <path d="M174 356L150 360M174 356L198 352" strokeWidth="2" />
          </g>
          <g transform="translate(0, -24)">
            <path d="M175 316C186 314 198 310 206 302" strokeWidth="1.7" />
            <path d="M174 336C166 348 160 366 158 386" strokeWidth="1.7" />
          </g>
          {/* İliak → femoral */}
          <path d="M173 424L142 470M173 424L198 470" strokeWidth="2.8" />
          <path d="M142 470C137 512 132 560 130 622" strokeWidth="1.9" />
          <path d="M198 470C203 512 208 560 210 622" strokeWidth="1.9" />
        </g>

        {/* Aortada akış animasyonu */}
        <path
          d="M176 190C175 244 173 310 173 424"
          fill="none"
          stroke={vessel}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeDasharray="7 17"
          className="anatomy-flow"
          pointerEvents="none"
        />

        {/* ══════════ 5. ORGANLAR ══════════ */}

        {/* Beyin — serebrum, serebellum, beyin sapı */}
        <Organ
          id="beyin"
          label="Merkezi sinir sistemi"
          d="M170 12C148 12 134 26 134 43C134 54 141 63 151 66L189 66C199 63 206 54 206 43C206 26 192 12 170 12Z
             M151 66C143 69 143 79 153 81L187 81C197 79 197 69 189 66Z
             M164 81L176 81L175 96L165 96Z"
        />

        {/* Tiroid — iki lob + istmus, trakea üzerinde */}
        <Organ
          id="tiroid"
          label="Tiroid"
          d="M163 98C154 97 148 105 149 114C150 123 157 127 162 123C167 119 167 109 166 103Z
             M177 98C186 97 192 105 191 114C190 123 183 127 178 123C173 119 173 109 174 103Z
             M166 108H174V117H166Z"
        />

        {/* Sağ akciğer (izleyicinin solu) — 3 loblu */}
        <Organ
          id="akciger"
          label="Sağ akciğer — üst, orta, alt lob"
          d="M152 112C139 116 127 131 120 152C113 174 107 198 106 220C106 230 108 236 111 240
             C124 234 138 230 152 236C157 229 159 208 160 186C161 158 160 129 158 118
             C157 112 155 111 152 112Z"
        />

        {/* Sol akciğer (izleyicinin sağı) — 2 loblu; medial kenarda kardiyak çentik */}
        <Organ
          id="akciger"
          label="Sol akciğer — üst ve alt lob, kardiyak çentik"
          d="M188 112C201 116 213 131 220 152C227 174 233 198 234 220C234 230 232 236 229 240
             C216 234 202 230 188 236C185 229 183 216 183 206C196 200 199 190 197 180
             C195 170 186 168 183 172C182 150 183 126 185 118C186 112 186 111 188 112Z"
        />

        {/* Kalp — tabanı yukarıda, apeksi aşağı-sağda (hastanın solu) */}
        <g className="anatomy-heart" style={{ transformOrigin: "180px 205px" }}>
          <Organ
            id="kalp"
            label="Kalp"
            d="M162 176C154 183 152 197 156 210C162 226 176 238 190 240C197 241 202 235 204 224
               C208 205 208 187 203 178C197 169 185 167 175 171C169 173 165 174 162 176Z"
          />
        </g>

        {/* ── Üst karın ──
            Diyaframın hemen altında, ALT KABURGALARIN ARKASINDA durur. Kafesin
            tümüyle altına yerleştirildiğinde organlar karına sarkmış görünüyordu;
            bu yüzden blok kostal kavisin içine çekildi. */}
        <g transform="translate(0, -24)">
        {/* Karaciğer — kubbeli üst yüz, keskin alt kenar; sol lob orta hattı geçer */}
        <Organ
          id="karaciger"
          label="Karaciğer"
          animate="filter"
          d="M104 264C97 269 95 282 98 296C103 315 114 330 130 336C149 343 172 341 187 331
             C196 325 198 315 192 307C184 297 173 292 167 282C161 271 149 262 134 260C122 258 111 259 104 264Z"
        />

        {/* Safra kesesi — karaciğerin alt yüzünde */}
        <Organ
          id="safra"
          label="Safra kesesi"
          d="M140 327C133 329 131 340 135 347C139 354 148 354 152 347C155 341 152 331 146 327Z"
        />

        {/* Mide — fundus sağ üstte, pilor orta hatta */}
        <Organ
          id="mide"
          label="Mide"
          d="M197 261C213 259 228 272 231 291C234 311 226 329 211 337C200 342 189 340 185 332
             C182 325 187 317 195 313C204 308 209 298 207 289C205 279 199 272 191 268C192 264 194 261 197 261Z"
        />

        {/* Dalak — sol hipokondriyum, midenin lateralinde */}
        <Organ
          id="dalak"
          label="Dalak / lenf sistemi"
          d="M226 276C237 273 244 284 243 297C242 311 234 318 227 314C220 310 217 296 219 286C220 281 223 277 226 276Z"
        />

        {/* Pankreas — başı duodenal kıvrımda, kuyruğu dalağa uzanır */}
        <Organ
          id="pankreas"
          label="Pankreas"
          d="M149 342C141 342 137 350 140 357C143 364 151 366 159 364C176 360 195 354 212 346
             C223 341 231 336 229 330C227 324 219 325 211 329C196 337 178 343 163 344C157 344 153 342 149 342Z"
        />

        </g>

        {/* ── Retroperiton: sürrenal bezler, böbrekler, üreterler ──
            Kendi kaydırması var. Böbrekler 11-12. kaburga hizasındadır; üst karın
            bloğuyla aynı yükseklikte bırakıldığında karın boşluğunun çok altına
            düşüyor, neredeyse pelvise oturuyorlardı. */}
        <g transform="translate(0, -42)">

        {/* Sürrenal bezler — böbrek üst kutbuna oturan başlıklar */}
        <Organ
          id="bobrek"
          label="Sağ sürrenal bez"
          d="M118 330C117 320 127 314 136 318C143 321 146 327 144 331C135 326 125 326 118 330Z"
        />
        <Organ
          id="bobrek"
          label="Sol sürrenal bez"
          d="M222 324C223 314 213 308 204 312C197 315 194 321 196 325C205 320 215 320 222 324Z"
        />

        {/* Böbrekler — hilus orta hatta bakar; sağ böbrek karaciğer nedeniyle alçak */}
        <Organ
          id="bobrek"
          label="Sağ böbrek"
          animate="filter"
          d="M134 333C121 333 115 346 115 361C115 376 121 389 134 389C142 389 147 384 147 378
             C147 371 140 368 140 361C140 354 147 351 147 344C147 338 142 333 134 333Z"
        />
        <Organ
          id="bobrek"
          label="Sol böbrek"
          animate="filter"
          d="M206 327C219 327 225 340 225 355C225 370 219 383 206 383C198 383 193 378 193 372
             C193 365 200 362 200 355C200 348 193 345 193 338C193 332 198 327 206 327Z"
        />

        {/* Üreterler */}
        <g fill="none" stroke={fillOf("bobrek")} strokeWidth="1.8" opacity="0.65" pointerEvents="none">
          <path d="M146 382C152 412 158 448 163 484" />
          <path d="M194 378C188 410 182 446 177 484" />
        </g>
        </g>

        {/* ── Pelvis ──
            Kaburga kavisiyle uyluk arasındaki boşluğun ortasına oturur. Bağırsak
            grubundan daha yukarı kaydırılır: aynı grupta olduğunda kasık
            hizasına sarkıyordu. */}
        <g transform="translate(0, -40)">

        {/* Pelvis — kemik iliğinin ana deposu; pelvik giriş ve obturator delikleri.
            Bağırsaklardan ÖNCE çizilir: çekum ve sigmoid pelvisin önünde durur. */}
        <Organ
          id="kemik"
          label="Kemik iliği — pelvis"
          d="M170 396C195 392 222 401 230 421C236 439 227 459 209 471C195 481 182 487 170 487
             C158 487 145 481 131 471C113 459 104 439 110 421C118 401 145 392 170 396Z
             M170 402C152 402 141 410 143 418C147 426 158 431 170 431C182 431 193 426 197 418C199 410 188 402 170 402Z
             M139 436C130 443 132 456 145 464C154 469 161 467 161 458C161 447 152 439 139 436Z
             M201 436C210 443 208 456 195 464C186 469 179 467 179 458C179 447 188 439 201 436Z"
        />
        </g>

        {/* ── Bağırsaklar ve mesane ── */}
        <g transform="translate(0, -20)">

        {/* Kalın bağırsak — çıkan, transvers (sarkık), inen, sigmoid, rektum */}
        <Organ
          id="mide"
          label="Kalın bağırsak"
          line={12}
          d="M111 406L110 350C119 342 133 344 147 354C159 362 177 364 192 356C205 349 216 342 224 346
             L230 402C230 419 219 434 203 440C189 445 177 448 170 452L170 470"
        />
        {/* Çekum + apendiks */}
        <Organ
          id="mide"
          label="Çekum ve apendiks"
          line={10}
          d="M111 406C103 411 101 422 108 428C117 436 130 433 132 423C133 416 126 409 118 408
             M118 431C116 439 114 447 118 453"
        />

        {/* İnce bağırsak — kolon çerçevesinin içinde kıvrımlar */}
        <Organ
          id="mide"
          label="İnce bağırsak"
          line={8}
          d="M138 374C154 366 177 368 194 376C207 382 205 393 190 395C171 397 148 395 139 401
             C131 406 135 414 150 416C169 418 190 413 199 417C207 420 203 429 190 432
             C175 435 157 431 147 435"
        />

        {/* Mesane — pubis arkasında, pelvis halkasının içinde */}
        <Organ
          id="bobrek"
          label="Mesane"
          d="M170 444C161 444 155 451 156 458C157 466 163 470 170 470C177 470 183 466 184 458C185 451 179 444 170 444Z"
        />
        </g>

        {/* İskelet kası — uyluk kas grupları */}
        {[undefined, MIRROR].map((t, i) => (
          <Organ
            key={i}
            id="kas"
            label={`İskelet kası — ${i === 0 ? "sağ" : "sol"} uyluk`}
            transform={t}
            d="M118 482C108 488 105 506 107 528C109 550 115 566 123 570C130 573 136 567 137 555
               C139 532 136 502 130 488C127 482 121 481 118 482Z"
          />
        ))}

        {/* ══════════ 6. KABURGA KAFESİ (organların önünde, yarı saydam) ══════════ */}
        <g fill="none" stroke={BONE_EDGE} strokeWidth="3.2" strokeLinecap="round" opacity="0.55" pointerEvents="none">
          {RIBS.map((rib, i) => (
            <g key={i}>
              <path d={rib.left} />
              <path d={rib.right} />
            </g>
          ))}
          {/* Kostal kavis — 8-10. kaburga kıkırdakları */}
          <path d="M160 236C146 244 128 242 110 218" strokeWidth="2.6" />
          <path d="M180 236C194 244 212 242 230 218" strokeWidth="2.6" />
        </g>
        {/* Sternum — manubrium, korpus, ksifoid */}
        <g fill={BONE} stroke={BONE_EDGE} strokeWidth="0.8" opacity="0.6" pointerEvents="none">
          <path d="M161 130h18l-2 16h-14zM163 150h14l-2 62h-10zM166 216h8l-3 12h-2z" />
        </g>

        {/* ══════════ 7. İÇ AYRINTILAR (tıklanamaz) ══════════ */}
        <g fill="none" stroke={STROKE} strokeWidth="1" opacity="0.6" pointerEvents="none">
          {/* Serebral girus izleri */}
          <path d="M170 14V64M153 24C163 31 163 45 153 52M187 24C177 31 177 45 187 52" strokeWidth="0.8" />
          {/* Akciğer fissürleri — sağda oblik + horizontal, solda yalnız oblik */}
          <path d="M112 158C124 184 137 210 148 232" />
          <path d="M116 176C129 180 143 180 155 177" />
          <path d="M228 158C217 182 206 206 196 226" />
          {/* Trakea + ana bronşlar */}
          <path d="M170 118V152M170 152L150 168M170 152L190 168" strokeWidth="1.2" opacity="0.55" />
          {/* Koroner damarlar */}
          <path d="M181 180C177 198 180 220 189 236M166 194C177 200 191 198 200 191" stroke={ARTERY} opacity="0.5" />
          {/* Diyafragma kubbesi */}
          <path d="M108 250C128 232 150 227 170 230C192 227 214 234 232 250" strokeWidth="1.4" strokeDasharray="4 3" opacity="0.5" />
          {/* Üst karın ayrıntıları — organ bloğuyla aynı ölçüde kaydırılır */}
          <g transform="translate(0, -24)">
            {/* Karaciğer — falsiform ligament */}
            <path d="M162 266C160 286 158 310 157 336" />
            {/* Safra ve pankreas kanalları */}
            <path d="M148 332C156 336 162 342 165 350" strokeWidth="0.9" />
            <path d="M152 352C172 348 194 342 219 332" strokeWidth="0.9" strokeDasharray="3 2" />
            {/* Mide rugaları */}
            <path d="M204 277C212 283 216 293 215 303M196 289C204 293 208 301 207 309" strokeWidth="0.9" opacity="0.45" />
          </g>
          {/* Böbrek hilusu — retroperiton bloğuyla aynı yükseklikte */}
          <g transform="translate(0, -42)">
            <path d="M138 352C132 356 130 366 134 372M202 346C208 350 210 360 206 366" strokeWidth="0.9" />
          </g>
          {/* Haustra — kolon segment çizgileri */}
          <g transform="translate(0, -20)">
            <path
              d="M104 362H117M104 378H117M104 394H117M237 362H224M237 378H224M237 394H224
                 M132 350V362M154 358V370M180 360V372M206 350V362"
              strokeWidth="0.9"
              opacity="0.4"
            />
          </g>
        </g>

        {/* ══════════ 8. BACAK KEMİKLERİ ══════════ */}
        <g fill={BONE} stroke={BONE_EDGE} strokeWidth="0.7" opacity="0.7">
          {[undefined, MIRROR].map((t, i) => (
            <g key={i} transform={t}>
              {/* Femur boynu + şaft */}
              <path d="M119 470C111 474 109 484 114 491C118 498 121 514 122 532C124 550 125 562 126 572L138 572C137 557 135 539 133 520C131 500 129 484 127 472Z" />
              {/* Patella */}
              <ellipse cx="132" cy="581" rx="7" ry="6" />
              {/* Tibia + fibula */}
              <path d="M126 590C125 606 123 624 122 640C122 646 122 650 122 653L134 653C134 649 134 645 134 640C135 623 136 606 137 590Z" />
            </g>
          ))}
        </g>

        <text x="170" y="692" textAnchor="middle" className="anatomy-caption">
          önden görünüm · izleyicinin solu = hastanın sağı
        </text>
      </svg>
    </FigureContext.Provider>
  );
}
