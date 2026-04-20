import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link2, Link2Off, Pencil, Plus, Trash2, Video } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import DataTable, { type Column } from '@/components/data/DataTable';
import type { Camera, PaginatedCameras, PaginatedPrinters } from '@/types';

type ModalMode = 'create' | 'edit' | null;

const emptyForm = {
  name: '',
  slug: '',
  go2rtc_base_url: '',
  stream_name: '',
  printer_id: '',
  notes: '',
};

export default function CamerasPage() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<ModalMode>(null);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [snapshotPreview, setSnapshotPreview] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const { data: camerasData, isLoading } = useQuery<PaginatedCameras>({
    queryKey: ['cameras'],
    queryFn: () => api.get('/cameras?limit=100').then((r) => r.data),
  });

  const { data: printersData } = useQuery<PaginatedPrinters>({
    queryKey: ['printers-for-cameras'],
    queryFn: () => api.get('/printers?is_active=true&limit=100').then((r) => r.data),
  });

  const cameras = camerasData?.items ?? [];
  const printers = printersData?.items ?? [];

  // Filter out printers already assigned to OTHER cameras
  const availablePrinters = printers.filter((p) => {
    if (form.printer_id && form.printer_id === p.id) return true; // Current assignment is OK
    return !cameras.some((c) => c.printer_id === p.id && c.id !== editId && c.is_active);
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        name: form.name.trim(),
        slug: form.slug.trim(),
        go2rtc_base_url: form.go2rtc_base_url.trim().replace(/\/+$/, ''),
        stream_name: form.stream_name.trim(),
        notes: form.notes.trim() || null,
      };
      if (form.printer_id) {
        payload.printer_id = form.printer_id;
      } else if (modal === 'edit') {
        payload.clear_printer_id = true;
      }

      if (modal === 'create') {
        return api.post('/cameras', payload);
      }
      return api.put(`/cameras/${editId}`, payload);
    },
    onSuccess: () => {
      toast.success(modal === 'create' ? 'Camera created' : 'Camera updated');
      qc.invalidateQueries({ queryKey: ['cameras'] });
      qc.invalidateQueries({ queryKey: ['printers'] });
      closeModal();
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || 'Failed to save camera');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/cameras/${id}`),
    onSuccess: () => {
      toast.success('Camera deactivated');
      qc.invalidateQueries({ queryKey: ['cameras'] });
      qc.invalidateQueries({ queryKey: ['printers'] });
    },
  });

  const closeModal = () => {
    setModal(null);
    setEditId(null);
    setForm(emptyForm);
    setErrors({});
    if (snapshotPreview) URL.revokeObjectURL(snapshotPreview);
    setSnapshotPreview(null);
    setPreviewLoading(false);
    setPreviewError(null);
  };

  const openCreate = () => {
    setForm(emptyForm);
    setModal('create');
  };

  const openEdit = (cam: Camera) => {
    setForm({
      name: cam.name,
      slug: cam.slug,
      go2rtc_base_url: cam.go2rtc_base_url,
      stream_name: cam.stream_name,
      printer_id: cam.printer_id ?? '',
      notes: cam.notes ?? '',
    });
    setEditId(cam.id);
    setModal('edit');
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.name.trim()) e.name = 'Name is required';
    if (!form.slug.trim()) e.slug = 'Slug is required';
    if (!form.go2rtc_base_url.trim()) e.go2rtc_base_url = 'go2rtc URL is required';
    if (!form.stream_name.trim()) e.stream_name = 'Stream name is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSave = () => {
    if (!validate()) return;
    saveMutation.mutate();
  };

  // Auto-generate slug from name
  const handleNameChange = (name: string) => {
    const slug = name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    setForm((f) => ({ ...f, name, slug }));
  };

  // Fetch snapshot preview through backend proxy to avoid CORS/mixed-content issues
  const fetchPreview = async () => {
    const baseUrl = form.go2rtc_base_url.trim().replace(/\/+$/, '');
    const stream = form.stream_name.trim();
    if (!baseUrl || !stream) return;

    setPreviewLoading(true);
    setPreviewError(null);
    setSnapshotPreview(null);
    try {
      const resp = await api.post('/cameras/test-snapshot', {
        go2rtc_base_url: baseUrl,
        stream_name: stream,
      }, { responseType: 'blob' });
      const url = URL.createObjectURL(resp.data);
      setSnapshotPreview(url);
    } catch {
      setPreviewError('Could not reach camera. Verify the go2rtc URL and stream name.');
    } finally {
      setPreviewLoading(false);
    }
  };

  // Auto-preview when both fields are filled (debounced)
  useEffect(() => {
    const baseUrl = form.go2rtc_base_url.trim();
    const stream = form.stream_name.trim();
    if (!baseUrl || !stream) {
      setSnapshotPreview(null);
      setPreviewError(null);
      return;
    }
    const timer = setTimeout(fetchPreview, 800);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.go2rtc_base_url, form.stream_name]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-semibold">Cameras</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage camera feeds and assign them to printers for live monitoring.
          </p>
        </div>
        <Button type="button" onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add Camera
        </Button>
      </div>

      <CamerasTable
        cameras={cameras}
        isLoading={isLoading}
        onEdit={openEdit}
        onDeactivate={(id) => deleteMutation.mutate(id)}
      />

      <Dialog open={Boolean(modal)} onOpenChange={(o) => !o && closeModal()}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{modal === 'create' ? 'Add camera' : 'Edit camera'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-5">

              {/* Name */}
              <div className="space-y-1.5">
                <Label htmlFor="camera-name">Name</Label>
                <Input
                  id="camera-name"
                  type="text"
                  value={form.name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="Wyze Cam - Bay 1"
                  invalid={Boolean(errors.name)}
                />
                {errors.name && <p className="text-xs text-danger">{errors.name}</p>}
              </div>

              {/* Slug */}
              <div className="space-y-1.5">
                <Label htmlFor="camera-slug">Slug</Label>
                <Input
                  id="camera-slug"
                  type="text"
                  value={form.slug}
                  onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                  placeholder="wyze-cam-bay-1"
                  invalid={Boolean(errors.slug)}
                />
                {errors.slug && <p className="text-xs text-danger">{errors.slug}</p>}
              </div>

              {/* go2rtc Base URL */}
              <div className="space-y-1.5">
                <Label htmlFor="camera-base-url">go2rtc Base URL</Label>
                <Input
                  id="camera-base-url"
                  type="text"
                  value={form.go2rtc_base_url}
                  onChange={(e) => setForm((f) => ({ ...f, go2rtc_base_url: e.target.value }))}
                  placeholder="http://192.168.1.50:1984"
                  className="font-mono"
                  invalid={Boolean(errors.go2rtc_base_url)}
                />
                {errors.go2rtc_base_url && (
                  <p className="text-xs text-danger">{errors.go2rtc_base_url}</p>
                )}
              </div>

              {/* Stream Name */}
              <div className="space-y-1.5">
                <Label htmlFor="camera-stream">Stream Name</Label>
                <Input
                  id="camera-stream"
                  type="text"
                  value={form.stream_name}
                  onChange={(e) => setForm((f) => ({ ...f, stream_name: e.target.value }))}
                  placeholder="wyze_printer_1"
                  className="font-mono"
                  invalid={Boolean(errors.stream_name)}
                />
                {errors.stream_name && (
                  <p className="text-xs text-danger">{errors.stream_name}</p>
                )}
              </div>

              {/* Snapshot Preview */}
              {(form.go2rtc_base_url.trim() && form.stream_name.trim()) && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <Label>Preview</Label>
                    <button
                      type="button"
                      onClick={fetchPreview}
                      disabled={previewLoading}
                      className="text-xs text-primary hover:text-primary/80 transition-colors disabled:opacity-50"
                    >
                      {previewLoading ? 'Loading...' : 'Refresh'}
                    </button>
                  </div>
                  <div className="rounded-lg overflow-hidden border border-border bg-black aspect-video flex items-center justify-center">
                    {previewLoading && (
                      <div className="text-muted-foreground text-sm animate-pulse">Fetching snapshot...</div>
                    )}
                    {!previewLoading && previewError && (
                      <div className="text-center px-4">
                        <p className="text-danger text-sm">{previewError}</p>
                        <button
                          type="button"
                          onClick={fetchPreview}
                          className="text-xs text-primary mt-2 hover:underline"
                        >
                          Try again
                        </button>
                      </div>
                    )}
                    {!previewLoading && !previewError && snapshotPreview && (
                      <img
                        src={snapshotPreview}
                        alt="Camera preview"
                        className="w-full h-full object-contain"
                      />
                    )}
                    {!previewLoading && !previewError && !snapshotPreview && (
                      <div className="text-muted-foreground text-xs">Waiting for snapshot...</div>
                    )}
                  </div>
                </div>
              )}

              {/* Assigned Printer */}
              <div className="space-y-1.5">
                <Label htmlFor="camera-printer">Assigned Printer</Label>
                <select
                  id="camera-printer"
                  value={form.printer_id}
                  onChange={(e) => setForm((f) => ({ ...f, printer_id: e.target.value }))}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">None (unassigned)</option>
                  {availablePrinters.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} {p.location ? `(${p.location})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Notes */}
              <div className="space-y-1.5">
                <Label htmlFor="camera-notes">Notes</Label>
                <Textarea
                  id="camera-notes"
                  value={form.notes}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  rows={2}
                  className="resize-none"
                />
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  Cancel
                </button>
                <Button
                  type="button"
                  onClick={handleSave}
                  disabled={saveMutation.isPending}
                >
                  {saveMutation.isPending ? 'Saving...' : modal === 'create' ? 'Add Camera' : 'Save Changes'}
                </Button>
              </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface CamerasTableProps {
  cameras: Camera[];
  isLoading: boolean;
  onEdit: (cam: Camera) => void;
  onDeactivate: (id: string) => void;
}

function CamerasTable({ cameras, isLoading, onEdit, onDeactivate }: CamerasTableProps) {
  const columns: Column<Camera>[] = [
    {
      key: 'name',
      header: 'Name',
      cell: (cam) => (
        <div className="flex items-center gap-2">
          <Video className="h-4 w-4 text-info shrink-0" />
          <span className="font-medium">{cam.name}</span>
        </div>
      ),
    },
    {
      key: 'stream',
      header: 'Stream',
      colClassName: 'hidden md:table-cell',
      cell: (cam) => (
        <code className="text-xs bg-muted/50 px-1.5 py-0.5 rounded">{cam.stream_name}</code>
      ),
    },
    {
      key: 'printer',
      header: 'Printer',
      cell: (cam) =>
        cam.printer_name ? (
          <span className="inline-flex items-center gap-1 text-primary">
            <Link2 className="h-3 w-3" />
            {cam.printer_name}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Link2Off className="h-3 w-3" />
            Unassigned
          </span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      colClassName: 'hidden sm:table-cell',
      cell: (cam) => (
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
            cam.is_active ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
          }`}
        >
          {cam.is_active ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      width: '96px',
      cell: (cam) => (
        <div className="flex items-center justify-end gap-1">
          <button
            type="button"
            onClick={() => onEdit(cam)}
            aria-label={`Edit ${cam.name}`}
            title="Edit"
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted transition-colors"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => onDeactivate(cam.id)}
            aria-label={`Deactivate ${cam.name}`}
            title="Deactivate"
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-danger/10 text-danger transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <DataTable<Camera>
      data={cameras}
      columns={columns}
      rowKey={(cam) => cam.id}
      loading={isLoading}
      emptyState="No cameras yet — add your first camera to start monitoring printers with live video."
    />
  );
}
