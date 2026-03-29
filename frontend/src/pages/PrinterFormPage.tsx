import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import type { Printer } from '@/types';

const STATUS_OPTIONS = ['idle', 'printing', 'paused', 'maintenance', 'offline', 'error'] as const;

const emptyForm = {
  name: '',
  slug: '',
  manufacturer: '',
  model: '',
  serial_number: '',
  location: '',
  status: 'idle',
  is_active: true,
  notes: '',
};

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120);
}

export default function PrinterFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: printer, isLoading } = useQuery<Printer>({
    queryKey: ['printer', id],
    queryFn: () => api.get(`/printers/${id}`).then((response) => response.data),
    enabled: isEdit,
  });

  const [form, setForm] = useState(emptyForm);
  const [slugTouched, setSlugTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!printer) return;
    setForm({
      name: printer.name,
      slug: printer.slug,
      manufacturer: printer.manufacturer || '',
      model: printer.model || '',
      serial_number: printer.serial_number || '',
      location: printer.location || '',
      status: printer.status,
      is_active: printer.is_active,
      notes: printer.notes || '',
    });
    setSlugTouched(true);
  }, [printer]);

  useEffect(() => {
    if (slugTouched) return;
    setForm((current) => ({ ...current, slug: slugify(current.name) }));
  }, [form.name, slugTouched]);

  const title = useMemo(() => (isEdit ? 'Edit Printer' : 'Add Printer'), [isEdit]);

  const update = (field: string, value: string | boolean) => {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: '' }));
  };

  const validate = () => {
    const nextErrors: Record<string, string> = {};
    if (!form.name.trim()) nextErrors.name = 'Name is required';
    if (!form.slug.trim()) nextErrors.slug = 'Slug is required';
    if (form.slug && !/^[a-z0-9-]+$/.test(form.slug)) nextErrors.slug = 'Use lowercase letters, numbers, and hyphens only';
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;

    setSaving(true);
    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        slug: form.slug.trim(),
        manufacturer: form.manufacturer.trim() || null,
        model: form.model.trim() || null,
        serial_number: form.serial_number.trim() || null,
        location: form.location.trim() || null,
        notes: form.notes.trim() || null,
      };

      if (isEdit) {
        await api.put(`/printers/${id}`, payload);
        toast.success('Printer updated');
        queryClient.invalidateQueries({ queryKey: ['printer', id] });
      } else {
        const response = await api.post('/printers', payload);
        toast.success('Printer created');
        queryClient.invalidateQueries({ queryKey: ['printers'] });
        navigate(`/printers/${response.data.id}`);
        return;
      }

      queryClient.invalidateQueries({ queryKey: ['printers'] });
      navigate(`/printers/${id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save printer');
    } finally {
      setSaving(false);
    }
  };

  if (isEdit && isLoading) {
    return <div className="rounded-lg border border-border bg-card p-6">Loading printer...</div>;
  }

  if (isEdit && !printer) {
    return <p className="py-16 text-center text-muted-foreground">Printer not found</p>;
  }

  const inputClass = (field: string) => `w-full rounded-md border px-3 py-2 bg-background focus:outline-none focus:ring-2 focus:ring-ring ${errors[field] ? 'border-destructive' : 'border-input'}`;

  return (
    <div className="max-w-3xl mx-auto">
      <Link to={isEdit && id ? `/printers/${id}` : '/printers'} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4 no-underline">
        <ArrowLeft className="w-4 h-4" /> Back
      </Link>

      <div className="rounded-lg border border-border bg-card p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">Track machine details, availability, and where this printer lives.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium mb-1.5">Name *</label>
              <input value={form.name} onChange={(e) => update('name', e.target.value)} className={inputClass('name')} placeholder="Bambu X1C #1" />
              {errors.name && <p className="mt-1 text-xs text-destructive">{errors.name}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Slug *</label>
              <input
                value={form.slug}
                onChange={(e) => {
                  setSlugTouched(true);
                  update('slug', slugify(e.target.value));
                }}
                className={inputClass('slug')}
                placeholder="bambu-x1c-1"
              />
              {errors.slug && <p className="mt-1 text-xs text-destructive">{errors.slug}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Manufacturer</label>
              <input value={form.manufacturer} onChange={(e) => update('manufacturer', e.target.value)} className={inputClass('manufacturer')} placeholder="Bambu Lab" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Model</label>
              <input value={form.model} onChange={(e) => update('model', e.target.value)} className={inputClass('model')} placeholder="X1 Carbon" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Serial Number</label>
              <input value={form.serial_number} onChange={(e) => update('serial_number', e.target.value)} className={inputClass('serial_number')} placeholder="Optional" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Location</label>
              <input value={form.location} onChange={(e) => update('location', e.target.value)} className={inputClass('location')} placeholder="Print room shelf A" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Status</label>
              <select value={form.status} onChange={(e) => update('status', e.target.value)} className={inputClass('status')}>
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>{option.replace('_', ' ')}</option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <label className="inline-flex items-center gap-3 rounded-md border border-border px-4 py-3 w-full cursor-pointer hover:bg-accent/50">
                <input type="checkbox" checked={form.is_active} onChange={(e) => update('is_active', e.target.checked)} className="h-4 w-4" />
                <div>
                  <p className="text-sm font-medium">Active printer</p>
                  <p className="text-xs text-muted-foreground">Inactive printers stay in history but are hidden from active use.</p>
                </div>
              </label>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Notes</label>
            <textarea
              value={form.notes}
              onChange={(e) => update('notes', e.target.value)}
              rows={5}
              className={inputClass('notes')}
              placeholder="Nozzle size, preferred materials, maintenance notes, quirks, etc."
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={saving} className="cursor-pointer rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50">
              {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Printer'}
            </button>
            <button type="button" onClick={() => navigate(isEdit && id ? `/printers/${id}` : '/printers')} className="cursor-pointer rounded-md border border-border px-4 py-2 hover:bg-accent">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
