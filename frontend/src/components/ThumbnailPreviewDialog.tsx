import { useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useLanguage } from "../i18n/LanguageContext";

export interface PreviewEntry {
  thumbnail: string;
  title: string;
  // Zero-padded row number, exactly as the list shows it.
  label: string;
}

interface ThumbnailPreviewDialogProps {
  entries: PreviewEntry[];
  // Position within `entries`; null = closed.
  index: number | null;
  onIndexChange: (index: number) => void;
  onClose: () => void;
}

const ThumbnailPreviewDialog = ({ entries, index, onIndexChange, onClose }: ThumbnailPreviewDialogProps) => {
  const { t } = useLanguage();
  const open = index !== null && entries[index] !== undefined;
  const hasPrev = open && index > 0;
  const hasNext = open && index < entries.length - 1;

  const handlePrev = () => {
    if (hasPrev) onIndexChange(index - 1);
  };
  const handleNext = () => {
    if (hasNext) onIndexChange(index + 1);
  };
  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) onClose();
  };

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft" && hasPrev) onIndexChange(index - 1);
      else if (e.key === "ArrowRight" && hasNext) onIndexChange(index + 1);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, hasPrev, hasNext, index, onIndexChange]);

  if (!open) return null;
  const entry = entries[index];

  return (
    <Dialog open onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-xl gap-3 p-3">
        <DialogTitle className="pr-8 truncate leading-snug">
          {entry.label}. {entry.title}
        </DialogTitle>
        <DialogDescription className="sr-only">{t.playlist.previewHint}</DialogDescription>
        <div className="relative flex items-center justify-center rounded-lg bg-neutral-100 overflow-hidden">
          <img
            src={entry.thumbnail}
            referrerPolicy="no-referrer"
            alt={entry.title}
            className="max-h-[70vh] w-full object-contain"
          />
          <Button
            type="button"
            variant="secondary"
            size="icon"
            aria-label={t.playlist.previousItem}
            disabled={!hasPrev}
            onClick={handlePrev}
            className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="icon"
            aria-label={t.playlist.nextItem}
            disabled={!hasNext}
            onClick={handleNext}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <p className="m-0 text-center text-xs text-slate-500">
          {index + 1} / {entries.length}
        </p>
      </DialogContent>
    </Dialog>
  );
};

export default ThumbnailPreviewDialog;
