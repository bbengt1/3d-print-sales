import { useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Paperclip, Trash2, Upload, Download } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { getApiErrorMessage } from '@/lib/apiError';

export interface AttachmentRecord {
  id: string;
  scope: string;
  record_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  description: string | null;
  has_thumbnail: boolean;
  sha256: string;
  uploaded_at: string;
}

interface AttachmentsPanelProps {
  scope: string;
  recordId: string;
  /** Hide upload button in read-only mode. */
  readOnly?: boolean;
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AttachmentsPanel({ scope, recordId, readOnly = false }: AttachmentsPanelProps) {
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AttachmentRecord | null>(null);

  const { data, isLoading } = useQuery<AttachmentRecord[]>({
    queryKey: ['attachments', scope, recordId],
    queryFn: () => api.get(`/attachments/${scope}/${recordId}`).then((r) => r.data),
    enabled: Boolean(recordId),
  });

  const onSelect = async (file: File | null) => {
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append('file', file);
    try {
      await api.post(`/attachments/${scope}/${recordId}`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Attached');
      qc.invalidateQueries({ queryKey: ['attachments', scope, recordId] });
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Upload failed'));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const onDelete = async (a: AttachmentRecord) => {
    try {
      await api.delete(`/attachments/${a.id}`);
      toast.success('Removed');
      qc.invalidateQueries({ queryKey: ['attachments', scope, recordId] });
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to remove'));
    }
  };

  const onDownload = (a: AttachmentRecord) => {
    const token = localStorage.getItem('token');
    const url = `/api/v1/attachments/${a.id}/download`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => r.blob())
      .then((blob) => {
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl;
        link.download = a.filename;
        link.click();
        URL.revokeObjectURL(objectUrl);
      })
      .catch(() => toast.error('Download failed'));
  };

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-medium">
          <Paperclip className="h-4 w-4" /> Attachments {data && data.length > 0 ? `(${data.length})` : ''}
        </h3>
        {!readOnly && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={(e) => onSelect(e.target.files?.[0] ?? null)}
            />
            <Button
              size="sm"
              variant="outline"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="mr-2 h-3.5 w-3.5" />
              {uploading ? 'Uploading…' : 'Upload'}
            </Button>
          </>
        )}
      </div>
      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : !data || data.length === 0 ? (
        <div className="text-sm text-muted-foreground">No attachments yet.</div>
      ) : (
        <ul className="divide-y">
          {data.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 py-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{a.filename}</div>
                <div className="text-xs text-muted-foreground">
                  {a.content_type} · {fmtSize(a.size_bytes)} · {new Date(a.uploaded_at).toLocaleString()}
                </div>
              </div>
              <Button size="icon" variant="ghost" onClick={() => onDownload(a)} aria-label="Download">
                <Download className="h-4 w-4" />
              </Button>
              {!readOnly && (
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setPendingDelete(a)}
                  aria-label="Remove"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={Boolean(pendingDelete)}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title="Remove attachment?"
        description={pendingDelete ? `"${pendingDelete.filename}" will be removed.` : ''}
        confirmLabel="Remove"
        tone="destructive"
        onConfirm={() => {
          if (pendingDelete) onDelete(pendingDelete);
          setPendingDelete(null);
        }}
      />
    </div>
  );
}
