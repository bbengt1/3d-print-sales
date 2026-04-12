import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Camera as CameraIcon, Plus, Pencil, Trash2, Link2, Link2Off, Video } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
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
    setSnapshotPreview(null);
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

  // Preview snapshot when URL + stream name are filled
  useEffect(() => {
    if (form.go2rtc_base_url.trim() && form.stream_name.trim()) {
      const url = `${form.go2rtc_base_url.trim().replace(/\/+$/, '')}/api/frame.jpeg?src=${encodeURIComponent(form.stream_name.trim())}`;
      setSnapshotPreview(url);
    } else {
      setSnapshotPreview(null);
    }
  }, [form.go2rtc_base_url, form.stream_name]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">Cameras</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage camera feeds and assign them to printers for live monitoring.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Camera
        </button>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="animate-pulse space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 bg-muted/50 rounded-lg" />
          ))}
        </div>
      ) : cameras.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <CameraIcon className="h-12 w-12 mx-auto mb-3 opacity-40" />
          <p className="text-lg font-medium">No cameras yet</p>
          <p className="text-sm mt-1">Add your first camera to start monitoring printers with live video.</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left px-4 py-3 font-medium">Name</th>
                <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Stream</th>
                <th className="text-left px-4 py-3 font-medium">Printer</th>
                <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">Status</th>
                <th className="text-right px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((cam) => (
                <tr key={cam.id} className="border-b border-border/50 hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Video className="h-4 w-4 text-info shrink-0" />
                      <span className="font-medium">{cam.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <code className="text-xs bg-muted/50 px-1.5 py-0.5 rounded">{cam.stream_name}</code>
                  </td>
                  <td className="px-4 py-3">
                    {cam.printer_name ? (
                      <span className="flex items-center gap-1 text-primary">
                        <Link2 className="h-3 w-3" />
                        {cam.printer_name}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <Link2Off className="h-3 w-3" />
                        Unassigned
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        cam.is_active
                          ? 'bg-primary/10 text-primary'
                          : 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {cam.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => openEdit(cam)}
                        className="p-1.5 rounded hover:bg-muted transition-colors"
                        title="Edit"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteMutation.mutate(cam.id)}
                        className="p-1.5 rounded hover:bg-danger/10 text-danger transition-colors"
                        title="Deactivate"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-card border border-border rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6 space-y-5">
              <h2 className="text-lg font-display font-bold">
                {modal === 'create' ? 'Add Camera' : 'Edit Camera'}
              </h2>

              {/* Name */}
              <div>
                <label className="block text-sm font-medium mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="Wyze Cam - Bay 1"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                {errors.name && <p className="text-xs text-danger mt-1">{errors.name}</p>}
              </div>

              {/* Slug */}
              <div>
                <label className="block text-sm font-medium mb-1">Slug</label>
                <input
                  type="text"
                  value={form.slug}
                  onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                  placeholder="wyze-cam-bay-1"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                {errors.slug && <p className="text-xs text-danger mt-1">{errors.slug}</p>}
              </div>

              {/* go2rtc Base URL */}
              <div>
                <label className="block text-sm font-medium mb-1">go2rtc Base URL</label>
                <input
                  type="text"
                  value={form.go2rtc_base_url}
                  onChange={(e) => setForm((f) => ({ ...f, go2rtc_base_url: e.target.value }))}
                  placeholder="http://192.168.1.50:1984"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                {errors.go2rtc_base_url && (
                  <p className="text-xs text-danger mt-1">{errors.go2rtc_base_url}</p>
                )}
              </div>

              {/* Stream Name */}
              <div>
                <label className="block text-sm font-medium mb-1">Stream Name</label>
                <input
                  type="text"
                  value={form.stream_name}
                  onChange={(e) => setForm((f) => ({ ...f, stream_name: e.target.value }))}
                  placeholder="wyze_printer_1"
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                {errors.stream_name && (
                  <p className="text-xs text-danger mt-1">{errors.stream_name}</p>
                )}
              </div>

              {/* Snapshot Preview */}
              {snapshotPreview && (
                <div>
                  <label className="block text-sm font-medium mb-1">Preview</label>
                  <div className="rounded-lg overflow-hidden border border-border bg-black aspect-video">
                    <img
                      src={snapshotPreview}
                      alt="Camera preview"
                      className="w-full h-full object-contain"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Live snapshot from go2rtc. If blank, verify the URL and stream name.
                  </p>
                </div>
              )}

              {/* Assigned Printer */}
              <div>
                <label className="block text-sm font-medium mb-1">Assigned Printer</label>
                <select
                  value={form.printer_id}
                  onChange={(e) => setForm((f) => ({ ...f, printer_id: e.target.value }))}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
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
              <div>
                <label className="block text-sm font-medium mb-1">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  rows={2}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none"
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
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saveMutation.isPending}
                  className="px-5 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {saveMutation.isPending ? 'Saving...' : modal === 'create' ? 'Add Camera' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
