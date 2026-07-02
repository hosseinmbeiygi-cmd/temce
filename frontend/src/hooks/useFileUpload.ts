import { useState, useCallback } from 'react';
import { getStoredAuth } from '@/lib/api';

interface UseFileUploadOptions<T> {
  path: string;
  fieldName?: string;
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
}

interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export function useFileUpload<T = unknown>(options: UseFileUploadOptions<T>) {
  const { path, fieldName = 'file', onSuccess, onError } = options;
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<T | null>(null);

  const upload = useCallback(
    async (
      file: File,
      callbacks?: {
        onProgress?: (loaded: number, total: number) => void;
      }
    ): Promise<T> => {
      setIsUploading(true);
      setError(null);
      setProgress(null);

      const formData = new FormData();
      formData.append(fieldName, file);

      const auth = getStoredAuth();
      const token = auth?.access_token;

      const headers: HeadersInit = {};
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      const xhr = new XMLHttpRequest();

      const promise = new Promise<T>((resolve, reject) => {
        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable) {
            const loaded = event.loaded;
            const total = event.total;
            const percentage = Math.round((loaded / total) * 100);
            setProgress({ loaded, total, percentage });
            callbacks?.onProgress?.(loaded, total);
          }
        });

        xhr.addEventListener('load', () => {
          setIsUploading(false);
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const response = JSON.parse(xhr.responseText);
              setData(response);
              onSuccess?.(response);
              resolve(response);
            } catch {
              const err = new Error('Invalid response format');
              setError(err);
              onError?.(err);
              reject(err);
            }
          } else {
            let errorMsg = `Upload failed with status ${xhr.status}`;
            try {
              const errResponse = JSON.parse(xhr.responseText);
              errorMsg = errResponse.message || errorMsg;
            } catch {
              // ignore
            }
            const err = new Error(errorMsg);
            setError(err);
            onError?.(err);
            reject(err);
          }
        });

        xhr.addEventListener('error', () => {
          setIsUploading(false);
          const err = new Error('Network error');
          setError(err);
          onError?.(err);
          reject(err);
        });

        xhr.addEventListener('abort', () => {
          setIsUploading(false);
          const err = new Error('Upload aborted');
          setError(err);
          onError?.(err);
          reject(err);
        });

        const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        xhr.open('POST', `${apiBase}${path}`);
        Object.keys(headers).forEach((key) => {
          xhr.setRequestHeader(key, headers[key]);
        });
        xhr.send(formData);
      });

      return promise;
    },
    [path, fieldName, onSuccess, onError]
  );

  const reset = useCallback(() => {
    setIsUploading(false);
    setProgress(null);
    setError(null);
    setData(null);
  }, []);

  return {
    upload,
    reset,
    isUploading,
    progress,
    error,
    data,
  };
}