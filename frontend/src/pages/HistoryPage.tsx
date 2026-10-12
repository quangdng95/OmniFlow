import { useState } from "react";
import { toast } from "sonner";
import { Copy, Download, Trash2 } from "lucide-react";
import { type Page } from "../components/Header";
import AnimatedSection from "../components/AnimatedSection";
import PlatformTag from "../components/PlatformTag";
import SectionCard from "../components/SectionCard";
import { Button } from "@/components/ui/button";
import { useLanguage } from "../i18n/LanguageContext";
import { clearHistory, loadHistory, removeHistoryEntry, type HistoryEntry } from "../lib/history";

interface HistoryPageProps {
  onNavigate: (page: Page) => void;
  onOpenUrl: (url: string) => void;
}

const HistoryPage = ({ onNavigate: _onNavigate, onOpenUrl }: HistoryPageProps) => {
  const { t, language } = useLanguage();
  const [entries, setEntries] = useState<HistoryEntry[]>(loadHistory);

  const formatTime = (timestamp: number): string =>
    new Intl.DateTimeFormat(language, { dateStyle: "medium", timeStyle: "short" }).format(new Date(timestamp));

  const handleCopy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      toast.success(t.history.linkCopied);
    } catch {
      toast.error(t.history.copyFailed);
    }
  };

  const handleRemove = (url: string) => setEntries(removeHistoryEntry(url));

  const handleClearAll = () => {
    clearHistory();
    setEntries([]);
  };

  return (
    <div className="w-full flex flex-col gap-4">
      <AnimatedSection>
        <SectionCard className="p-5 md:p-6 flex flex-col gap-2">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <h3 className="text-lg font-bold text-ink m-0">{t.history.heading}</h3>
            {entries.length > 0 && (
              <Button
                variant="ghost"
                onClick={handleClearAll}
                className="text-destructive hover:bg-invalid hover:text-destructive gap-1.5"
              >
                <Trash2 className="h-4 w-4" />
                {t.history.clearAll}
              </Button>
            )}
          </div>
          <p className="text-base text-ink-muted leading-relaxed m-0">{t.history.intro}</p>
        </SectionCard>
      </AnimatedSection>

      {entries.length === 0 && (
        <AnimatedSection delay={0.05}>
          <SectionCard className="p-5 md:p-6">
            <p className="text-base text-ink-muted m-0 text-center">{t.history.empty}</p>
          </SectionCard>
        </AnimatedSection>
      )}

      {entries.map((entry, index) => (
        <AnimatedSection key={entry.url} delay={Math.min(index, 5) * 0.05}>
          <SectionCard className="p-4 bg-white border border-ink  rounded-none flex flex-col gap-3">
            <div className="flex items-start gap-3 min-w-0">
              <div className="h-12 w-12 rounded-none bg-muted shrink-0 border border-ink overflow-hidden">
                {entry.thumbnail && (
                  <img
                    src={entry.thumbnail}
                    referrerPolicy="no-referrer"
                    alt=""
                    className="h-full w-full object-cover"
                    onError={(event) => {
                      // Signed CDN thumbnails expire; fall back to the plain tile.
                      event.currentTarget.style.display = "none";
                    }}
                  />
                )}
              </div>
              <div className="flex-1 min-w-0 flex flex-col gap-1">
                <h4 className="text-base font-semibold text-ink leading-snug line-clamp-2 break-words m-0">
                  {entry.title || t.history.untitled}
                </h4>
                <p className="text-base text-ink-muted leading-snug truncate m-0" title={entry.url}>
                  {entry.url}
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  <PlatformTag platform={entry.platform} />
                  <span className="text-base text-ink-muted">{formatTime(entry.downloadedAt)}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <Button
                onClick={() => onOpenUrl(entry.url)}
                className="bg-ink text-on-ink hover:bg-ink-hover gap-1.5  rounded-none"
              >
                <Download className="h-4 w-4" />
                {t.history.downloadAgain}
              </Button>
              <Button
                variant="outline"
                onClick={() => void handleCopy(entry.url)}
                aria-label={`${t.history.copyLink}: ${entry.title || entry.url}`}
                className="gap-1.5 rounded-none border-ink text-ink "
              >
                <Copy className="h-4 w-4" />
                {t.history.copyLink}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleRemove(entry.url)}
                aria-label={`${t.history.remove}: ${entry.title || entry.url}`}
                className="text-ink-muted hover:bg-invalid hover:text-destructive ml-auto"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </SectionCard>
        </AnimatedSection>
      ))}
    </div>
  );
};

export default HistoryPage;
