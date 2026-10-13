import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useLanguage } from "../i18n/LanguageContext";
import {
  getSavePlatform,
  isAbortError,
  isNotAllowedError,
  sharePreparedSave,
  type PrepareOptions,
  type PreparedSave,
} from "../lib/saveFile";

type Preparer = (url: string, options: PrepareOptions) => Promise<PreparedSave>;

interface UsePreparedSaveResult {
  saving: boolean;
  failed: boolean;
  // iOS only: the file is being fetched ahead of the tap. `progress` is 0-100, or null while the size is unknown.
  preparing: boolean;
  progress: number | null;
  // iOS only: set once the file is ready for the share sheet - "photos" when every file is a video or
  // image (the sheet then offers Save Video / Save Image), "files" for audio and anything else.
  shareKind: "photos" | "files" | null;
  save: () => Promise<void>;
}

// Prepares a finished download as soon as its URL exists. On iOS that means fetching it into memory
// (with progress, abortable) so the user's tap can call navigator.share() immediately - Safari rejects a
// share() that is not inside the tap's short user-activation window (see sharePreparedSave). Everywhere
// else (and on iOS for a file that is too big) there is nothing to fetch: the tap streams the file to disk.
// If the tap still lands before the files are ready we wait, try once, and on NotAllowedError ask the
// user to tap again - the second tap then shares instantly from the cache.
export const usePreparedSave = (url: string | undefined, prepare: Preparer): UsePreparedSaveResult => {
  const { t } = useLanguage();
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [shareKind, setShareKind] = useState<"photos" | "files" | null>(null);
  const prepareRef = useRef(prepare);
  const preparedRef = useRef<PreparedSave | null>(null);
  const pendingRef = useRef<Promise<PreparedSave> | null>(null);

  useEffect(() => {
    prepareRef.current = prepare;
  }, [prepare]);

  useEffect(() => {
    preparedRef.current = null;
    pendingRef.current = null;
    setFailed(false);
    setShareKind(null);
    setPreparing(false);
    setProgress(null);
    if (!url) return;
    let stale = false;
    const controller = new AbortController();
    const isIos = getSavePlatform() === "ios";
    if (isIos) setPreparing(true);
    const pending = prepareRef.current(url, {
      signal: controller.signal,
      onProgress: (percent) => {
        if (!stale) setProgress(percent);
      },
    });
    pendingRef.current = pending;
    pending
      .then((prepared) => {
        if (stale) return;
        preparedRef.current = prepared;
        if (prepared.directUrl || prepared.files.length === 0) return;
        setShareKind(prepared.files.every((f) => /^(video|image)\//.test(f.type)) ? "photos" : "files");
      })
      .catch(() => {
        // Surfaced on tap instead - the tap retries the fetch.
        if (!stale) {
          pendingRef.current = null;
          setFailed(true);
        }
      })
      .finally(() => {
        if (!stale) setPreparing(false);
      });
    return () => {
      // A new video or a closed page: stop fetching and let the memory go.
      stale = true;
      controller.abort();
      preparedRef.current = null;
    };
  }, [url]);

  const handleShareError = (error: unknown) => {
    if (isNotAllowedError(error)) {
      toast.info(t.downloadSuccess.tapAgain);
    } else if (!isAbortError(error)) {
      // AbortError = the user backed out of the share sheet: a cancel, not a failure.
      setFailed(true);
      toast.error(error instanceof Error ? error.message : String(error));
    }
  };

  // sharePreparedSave resolves only once the user finished the share sheet (or the download link was
  // clicked); backing out rejects with AbortError and gets no message at all. After the share sheet
  // there is nothing to add; after a plain download the message depends on where the file went.
  const notifySaved = (result: "shared" | "downloaded") => {
    setFailed(false);
    if (result === "shared") {
      // The share sheet closed after the user picked an action: confirm it on the page too.
      toast.success(t.downloadSuccess.savedToDevice);
      return;
    }
    const platform = getSavePlatform();
    toast.success(
      platform === "ios"
        ? t.downloadSuccess.iosFiles
        : platform === "android"
          ? t.downloadSuccess.androidStarted
          : t.downloadSuccess.downloadStarted
    );
  };

  const save = async () => {
    if (!url) return;
    const ready = preparedRef.current;
    if (ready) {
      try {
        // No await before this call: share() has to run inside the tap.
        notifySaved(await sharePreparedSave(ready));
      } catch (error: unknown) {
        handleShareError(error);
      }
      return;
    }
    setSaving(true);
    try {
      const pending = pendingRef.current ?? prepareRef.current(url, {});
      pendingRef.current = pending;
      const prepared = await pending;
      preparedRef.current = prepared;
      notifySaved(await sharePreparedSave(prepared));
    } catch (error: unknown) {
      pendingRef.current = preparedRef.current ? pendingRef.current : null;
      handleShareError(error);
    } finally {
      setSaving(false);
    }
  };

  return { saving, failed, preparing, progress, shareKind, save };
};
