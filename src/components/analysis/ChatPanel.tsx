"use client";
import React, { useEffect, useRef, useState } from "react";
import { AlertTriangle, Loader2, Send, Sparkles } from "lucide-react";

import { chat, chatSuggestions, type ChatTurn } from "@/lib/api";
import { Panel } from "@/components/ui/Primitives";

interface ChatPanelProps {
  /** Kural motorunun ürettiği klinik özet; her soruda modele yeniden verilir. */
  brief: string;
  modelLabel: string;
}

/** Kullanıcı girdisi için üst sınır — backend de 500 karakterde kesiyor. */
const MAX_QUESTION_LENGTH = 500;

export function ChatPanel({ brief, modelLabel }: ChatPanelProps) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [question, setQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    chatSuggestions()
      .then((data) => !cancelled && setSuggestions(data.questions))
      .catch(() => undefined); // öneriler alınamazsa sohbet yine çalışır
    return () => {
      cancelled = true;
    };
  }, []);

  // Yeni mesaj geldiğinde en alta kaydır
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, isSending]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isSending) return;

    const history = turns;
    setTurns([...history, { role: "user", content: trimmed }]);
    setQuestion("");
    setError(null);
    setIsSending(true);

    try {
      const response = await chat(brief, trimmed, history);
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer }]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Yanıt alınamadı.");
      // Başarısız soruyu geri al ki kullanıcı tekrar deneyebilsin
      setTurns(history);
      setQuestion(trimmed);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <Panel
      title="Bulgularınız hakkında soru sorun"
      description={`${modelLabel} · yanıtlar yalnızca bu panele dayanır`}
      aside={<Sparkles size={14} className="text-accent" />}
    >
      {turns.length === 0 && (
        <p className="mb-4 text-[13px] leading-relaxed text-ink-muted">
          Sorularınız yalnızca yukarıdaki bulgularla sınırlıdır. Asistan ilaç veya doz önermez,
          teşhis koymaz.
        </p>
      )}

      {turns.length > 0 && (
        <div ref={listRef} className="mb-4 max-h-96 space-y-3 overflow-y-auto pr-1">
          {turns.map((turn, index) => (
            <div
              key={index}
              className={
                turn.role === "user"
                  ? "ml-auto max-w-[85%] rounded-lg rounded-br-sm bg-accent px-3.5 py-2.5 text-[13px] leading-relaxed text-white"
                  : "mr-auto max-w-[90%] whitespace-pre-line rounded-lg rounded-bl-sm border border-line bg-sunken px-3.5 py-2.5 text-[13px] leading-relaxed text-ink"
              }
            >
              {turn.content}
            </div>
          ))}
          {isSending && (
            <div className="mr-auto flex items-center gap-2 rounded-lg border border-line bg-sunken px-3.5 py-2.5 text-[13px] text-ink-subtle">
              <Loader2 size={13} className="animate-spin" />
              Yanıt hazırlanıyor…
            </div>
          )}
        </div>
      )}

      {suggestions.length > 0 && turns.length === 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {suggestions.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => send(item)}
              disabled={isSending}
              className="rounded-full border border-line bg-raised px-3 py-1.5 text-[12px] text-ink-muted transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
            >
              {item}
            </button>
          ))}
        </div>
      )}

      {error && (
        <p className="mb-3 flex items-start gap-2 rounded-md border border-warn-line bg-warn-soft px-3 py-2 text-[12px] text-ink-muted">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          {error}
        </p>
      )}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(question);
        }}
        className="flex items-end gap-2"
      >
        <div className="flex-1">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value.slice(0, MAX_QUESTION_LENGTH))}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                send(question);
              }
            }}
            rows={2}
            placeholder="Örn: AST yüksekliği ne anlama geliyor?"
            disabled={isSending}
            className="w-full resize-none rounded-md border border-line bg-sunken px-3 py-2 text-[13px] text-ink outline-none transition-colors placeholder:text-ink-subtle focus:border-accent disabled:opacity-60"
          />
          <p className="mt-1 text-[11px] text-ink-subtle">
            Enter ile gönder · {question.length}/{MAX_QUESTION_LENGTH}
          </p>
        </div>
        <button
          type="submit"
          disabled={isSending || !question.trim()}
          className="mb-6 inline-flex items-center gap-1.5 rounded-md bg-accent px-3.5 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-accent-hover disabled:opacity-40"
        >
          {isSending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          Gönder
        </button>
      </form>

      <p className="mt-3 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-subtle">
        Yapay zekâ yanıtları hata içerebilir. Bu bir teşhis değildir; kararlarınızı hekiminizle
        birlikte verin.
      </p>
    </Panel>
  );
}
