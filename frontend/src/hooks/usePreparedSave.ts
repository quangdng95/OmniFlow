import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useLanguage } from "../i18n/LanguageContext";
import { isNotAllowedError, sharePreparedSave, type PreparedSave } from "../lib/saveFile";

type Preparer = (url: string) => Promise<PreparedSave>;

interface UsePreparedSaveResult {
  saving: boolean;
  save: () => Promise<void>;
}

// Fetches (and unzips) a finished download as soon as its URL exists, so the
// user's tap on "Download" can call navigator.share() immediately - iOS
// Safari rejects a share() that isn't inside the tap's short user-activation
// window (see sharePreparedSave). If the tap still lands before the files
// are ready, we wait for them, try once, and on NotAllowedError ask the user
// to tap again - the second tap then shares instantly from the cache.
export const usePreparedSave = (url: string | undefined, prepare: Preparer): UsePreparedSaveResult => {
  const { t } = useLanguage();
  const [saving, setSaving] = useState(false);
  const prepareRef = useRef(prepare);
  const preparedRef = useRef<PreparedSave | null>(null);
  const pendingRef = useRef<Promise<PreparedSave> | null>(null);

  useEffect(() => {
    prepareRef.current = prepare;
  }, [prepare]);

  useEffect(() => {
    preparedRef.current = null;
    pendingRef.current = null;
    if (!url) return;
    let stale = false;
    const pending = prepareRef.current(url);
    pendingRef.current = pending;
    pending
      .then((prepared) => {
        if (!stale) preparedRef.current = prepared;
      })
      .catch(() => {
        // Surfaced on tap instead - the tap retries the fetch.
        if (!stale) pendingRef.current = null;
      });
    return () => {
      stale = true;
    };
  }, [url]);

  const handleShareError = (error: unknown) => {
    if (isNotAllowedError(error)) {
      toast.info(t.downloadSuccess.tapAgain);
    } else if (!(error instanceof Error && error.name === "AbortError")) {
      // AbortError = the user backed out of the share sheet: a cancel, not a failure.
      toast.error(error instanceof Error ? error.message : String(error));
    }
  };

  const save = async () => {
    if (!url) return;
    const ready = preparedRef.current;
    if (ready) {
      try {
        await sharePreparedSave(ready);
      } catch (error: unknown) {
        handleShareError(error);
      }
      return;
    }
    setSaving(true);
    try {
      const pending = pendingRef.current ?? prepareRef.current(url);
      pendingRef.current = pending;
      const prepared = await pending;
      preparedRef.current = prepared;
      await sharePreparedSave(prepared);
    } catch (error: unknown) {
      pendingRef.current = preparedRef.current ? pendingRef.current : null;
      handleShareError(error);
    } finally {
      setSaving(false);
    }
  };

  return { saving, save };
};
