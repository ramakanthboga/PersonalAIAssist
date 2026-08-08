"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Loader2, CheckCircle, XCircle } from "lucide-react";

interface UploadZoneProps {
  onUpload: (file: File) => Promise<void>;
}

/** Keep in sync with backend ALLOWED_EXTENSIONS / parser extractors. */
const ACCEPTED_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "text/plain": [".txt"],
  "text/markdown": [".md"],
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/tiff": [".tif", ".tiff"],
};

export default function UploadZone({ onUpload }: UploadZoneProps) {
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      setUploading(true);
      setStatus("idle");
      setErrorMsg("");

      try {
        for (const file of acceptedFiles) {
          await onUpload(file);
        }
        setStatus("success");
        setTimeout(() => setStatus("idle"), 3000);
      } catch (err) {
        setStatus("error");
        setErrorMsg(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [onUpload],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 50 * 1024 * 1024,
    disabled: uploading,
  });

  return (
    <div
      {...getRootProps()}
      className={`rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
        isDragActive
          ? "border-blue-500 bg-blue-500/10"
          : uploading
          ? "border-[hsl(var(--border))] opacity-50 cursor-wait"
          : "border-[hsl(var(--border))] hover:border-blue-500/50 hover:bg-[hsl(var(--muted)/0.3)]"
      }`}
    >
      <input {...getInputProps()} />

      {uploading ? (
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <p className="text-sm">Uploading...</p>
        </div>
      ) : status === "success" ? (
        <div className="flex flex-col items-center gap-2 text-green-400">
          <CheckCircle className="h-8 w-8" />
          <p className="text-sm">Uploaded successfully!</p>
        </div>
      ) : status === "error" ? (
        <div className="flex flex-col items-center gap-2 text-red-400">
          <XCircle className="h-8 w-8" />
          <p className="text-sm">{errorMsg}</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <Upload className="h-8 w-8 text-[hsl(var(--muted-foreground))]" />
          <p className="text-sm font-medium">
            {isDragActive ? "Drop files here" : "Drag & drop files, or click to browse"}
          </p>
          <p className="text-xs text-[hsl(var(--muted-foreground))]">
            PDF, DOCX, TXT, MD, CSV, XLSX, Images (max 50MB)
          </p>
        </div>
      )}
    </div>
  );
}
