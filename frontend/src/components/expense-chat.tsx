"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, MessageSquare, Send, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { apiError } from "@/lib/format";
import type { ChatMessage, ChatResponse, Insights } from "@/lib/types";
import { cn } from "@/lib/utils";

export const DATASET_STORAGE_KEY = "expense-analyzer-dataset-id";

const SUGGESTIONS = [
  "How much did I spend on Swiggy?",
  "Food vs Shopping this year",
  "Who is my top merchant?",
];

export function ExpenseChat({
  datasetId,
  insights,
  insightsSource,
}: {
  datasetId?: string | null;
  insights?: Insights | null;
  insightsSource?: string;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(Boolean(datasetId));
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!datasetId) {
      setMessages([]);
      setLoadingHistory(false);
      return;
    }
    let cancelled = false;
    setLoadingHistory(true);
    fetch(`/api/backend/datasets/${datasetId}/messages`)
      .then(async (res) => {
        const payload = await res.json();
        if (!res.ok) throw new Error(apiError(payload, "Could not load chat"));
        if (!cancelled) setMessages(payload as ChatMessage[]);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load chat");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [datasetId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, loading]);

  async function send(text: string) {
    if (!datasetId || !text || loading) return;
    setError("");
    setDraft("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);
    try {
      const res = await fetch(`/api/backend/datasets/${datasetId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(apiError(payload, "Chat failed"));
      }
      const data = payload as ChatResponse;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
      setMessages((prev) => prev.slice(0, -1));
      setDraft(text);
    } finally {
      setLoading(false);
    }
  }

  function onSend(e: React.FormEvent) {
    e.preventDefault();
    void send(draft.trim());
  }

  const ready = Boolean(datasetId);

  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
      <div className="flex items-start gap-3 border-b border-border px-4 py-3">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-background">
          <MessageSquare className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold tracking-tight">Ask the statement</h2>
          </div>
          <p className="text-xs text-muted-foreground">
            Grounded answers from this upload, not the chart filters.
          </p>
        </div>
      </div>

      {insights ? (
        <div className="border-b border-border px-4 py-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5" />
            Briefing
            {insightsSource ? (
              <Badge variant="outline" className="font-mono text-[10px]">
                {insightsSource}
              </Badge>
            ) : null}
          </div>
          <p className="text-sm font-medium leading-snug">{insights.headline}</p>
          {insights.highlights[0] ? (
            <p className="mt-1.5 text-xs text-muted-foreground">
              {insights.highlights[0]}
            </p>
          ) : null}
          {insights.watchouts?.[0] ? (
            <p className="mt-1.5 text-xs text-destructive/90">
              Watch: {insights.watchouts[0]}
            </p>
          ) : null}
        </div>
      ) : null}

      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-3 p-4">
          {!ready ? (
            <p className="text-sm text-muted-foreground">
              Upload a CSV on the left to chat about merchants, categories, and
              spend.
            </p>
          ) : loadingHistory ? (
            <p className="text-sm text-muted-foreground">Loading chat…</p>
          ) : messages.length === 0 ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Ask a question, or start with one of these:
              </p>
              <div className="flex flex-col gap-2">
                {SUGGESTIONS.map((prompt) => (
                  <Button
                    key={prompt}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-auto justify-start whitespace-normal py-2 text-left font-normal"
                    onClick={() => void send(prompt)}
                    disabled={loading}
                  >
                    {prompt}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={`${msg.role}-${i}-${msg.content.slice(0, 24)}`}
                className={cn(
                  "max-w-[92%] rounded-lg px-3 py-2 text-sm",
                  msg.role === "user"
                    ? "ml-auto bg-primary text-primary-foreground"
                    : "bg-muted/60 text-foreground",
                )}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))
          )}
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Looking up the statement…
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <Separator />
      <div className="p-3">
        {error ? <p className="mb-2 text-sm text-destructive">{error}</p> : null}
        <form className="flex gap-2" onSubmit={onSend}>
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={ready ? "Ask about spend…" : "Upload a statement first"}
            disabled={loading || !ready}
            maxLength={2000}
          />
          <Button
            type="submit"
            disabled={loading || !ready || !draft.trim()}
            size="icon"
          >
            <Send className="h-4 w-4" />
            <span className="sr-only">Send</span>
          </Button>
        </form>
      </div>
    </div>
  );
}
