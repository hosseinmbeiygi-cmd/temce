"use client";

import { useCallback, useRef, useState } from "react";

import { apiUpload } from "@/lib/api";

type Phase = "idle" | "loading" | "success" | "error";

export interface UseFileUploadOptions<T> {
  /** API path relative to /api/v1 (will be prefixed by the api client). */
  path: string;
  /** Field name used in the multipart body. Defaults to "file". */
  fieldName?: string;
  /**
   * Optional validator. Throw an Error to halt the upload with a friendly message;
   * mutate() will surface it via the `error` state without ever calling the API.
   */
  validate?: (file: File) => void | Promise<void>;
  /** Invoked after a successful response. Use this to e.g. invalidate queries. */
  onSuccess?: (data: T, file: File) => void | Promise<void>;
}

export interface UseFileUploadReturn<T> {
  phase: Phase;
  progress: number;
  error: string | null;
  data: T | null;
  file: File | null;
  /** Upload ``file``. Pass ``onProgress`` to forward progress events from the caller. */
  upload: (
    file: File,
    opts?: { onProgress?: (loaded: number, total: number) => void },
  ) => Promise<T | undefined>;
  reset: () => void;
}

/**
 * Tiny wrapper around ``apiUpload`` for React. Returns the current phase,
 * upload progress, the last error, and the parsed response. Designed to be
 * consumed either directly or behind a UI wrapper like <FileUpload />.
 */
export function useFileUpload<T = unknown>(
  options: UseFileUploadOptions<T>,
): UseFileUploadReturn<T> {
  const { path, fieldName = "file", validate, onSuccess } = options;

  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<T | null>(null);
  const [file, setFile] = useState<File | null>(null);

  // keep the latest validate/onSuccess without forcing consumers to memoize
  const validateRef = useRef(validate);
  const onSuccessRef = useRef(onSuccess);
  validateRef.current = validate;
  onSuccessRef.current = onSuccess;

  const reset = useCallback(() => {
    setPhase("idle");
    setProgress(0);
    setError(null);
    setData(null);
    setFile(null);
  }, []);

  const upload = useCallback(
    async (
      incoming: File,
      opts?: { onProgress?: (loaded: number, total: number) => void },
    ) => {
      setPhase("loading");
      setProgress(0);
      setError(null);
      setData(null);
      setFile(incoming);

      try {
        if (validateRef.current) {
          await validateRef.current(incoming);
        }

        const formData = new FormData();
        formData.append(fieldName, incoming);

        const result = await apiUpload<T>(path, formData, undefined, (loaded, total) => {
          const pct = total ? Math.round((loaded / total) * 100) : 0;
          setProgress(pct);
          opts?.onProgress?.(loaded, total);
        });

        setData(result);
        setProgress(100);
        setPhase("success");
        if (onSuccessRef.current) {
          await onSuccessRef.current(result, incoming);
        }
        return result;
      } catch (err) {
        // Record the error in hook state for any consumer that wants to render
        // it locally, then re-throw so the caller (typically <FileUpload />) sees
        // the *real* error message and can show it to the user instead of a
        // generic "upload failed" string.
        const wrapped: Error =
          err instanceof Error ? err : new Error("خطای ناشناخته");
        setError(wrapped.message);
        setPhase("error");
        throw wrapped;
      }
    },
    [path, fieldName],
  );

  return { phase, progress, error, data, file, upload, reset };
}
