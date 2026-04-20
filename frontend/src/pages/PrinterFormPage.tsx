import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, PlugZap } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import type { Printer, PrinterConnectionTestResult } from '@/types';

const STATUS_OPTIONS = ['idle', 'printing', 'paused', 'maintenance', 'offline', 'error'] as const;
const MONITOR_PROVIDER_OPTIONS = [
  { value: 'octoprint', label: 'OctoPrint', placeholder: 'http://octoprint.local', authHint: 'Optional API key if your OctoPrint instance requires one.' },
  { value: 'moonraker', label: 'Moonraker / Fluidd / Mainsail', placeholder: 'http://printer.local:7125', authHint: 'Usually no API key on LAN, but you can supply one if your Moonraker setup requires it.' },
] as const;

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
  monitor_enabled: false,
  monitor_provider: 'octoprint',
  monitor_base_url: '',
  monitor_api_key: '',
  clear_monitor_api_key: false,
  monitor_poll_interval_seconds: 30,
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
  const [testingConnection, setTestingConnection] = useState(false);
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
      monitor_enabled: printer.monitor_enabled,
      monitor_provider: printer.monitor_provider || 'octoprint',
      monitor_base_url: printer.monitor_base_url || '',
      monitor_api_key: '',
      clear_monitor_api_key: false,
      monitor_poll_interval_seconds: printer.monitor_poll_interval_seconds || 30,
    });
    setSlugTouched(true);
  }, [printer]);

  useEffect(() => {
    if (slugTouched) return;
    setForm((current) => ({ ...current, slug: slugify(current.name) }));
  }, [form.name, slugTouched]);

  const title = useMemo(() => (isEdit ? 'Edit Printer' : 'Add Printer'), [isEdit]);
  const selectedProvider = useMemo(
    () => MONITOR_PROVIDER_OPTIONS.find((option) => option.value === form.monitor_provider) ?? MONITOR_PROVIDER_OPTIONS[0],
    [form.monitor_provider],
  );

  const update = (field: string, value: string | boolean | number) => {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: '' }));
  };

  const validate = () => {
    const nextErrors: Record<string, string> = {};
    if (!form.name.trim()) nextErrors.name = 'Name is required';
    if (!form.slug.trim()) nextErrors.slug = 'Slug is required';
    if (form.slug && !/^[a-z0-9-]+$/.test(form.slug)) nextErrors.slug = 'Use lowercase letters, numbers, and hyphens only';
    if (form.monitor_enabled && !form.monitor_base_url.trim()) nextErrors.monitor_base_url = 'Base URL is required when monitoring is enabled';
    if (form.monitor_poll_interval_seconds < 5) nextErrors.monitor_poll_interval_seconds = 'Poll interval must be at least 5 seconds';
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const buildPayload = () => ({
    ...form,
    name: form.name.trim(),
    slug: form.slug.trim(),
    manufacturer: form.manufacturer.trim() || null,
    model: form.model.trim() || null,
    serial_number: form.serial_number.trim() || null,
    location: form.location.trim() || null,
    notes: form.notes.trim() || null,
    monitor_provider: form.monitor_enabled ? form.monitor_provider : null,
    monitor_base_url: form.monitor_enabled ? (form.monitor_base_url.trim() || null) : null,
    monitor_api_key: form.monitor_enabled && form.monitor_api_key.trim() ? form.monitor_api_key.trim() : undefined,
    clear_monitor_api_key: form.monitor_enabled ? form.clear_monitor_api_key : true,
  });

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;

    setSaving(true);
    try {
      const payload = buildPayload();

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

  const handleTestConnection = async () => {
    if (!validate()) return;

    try {
      setTestingConnection(true);

      if (isEdit && id) {
        const response = await api.post<PrinterConnectionTestResult>(`/printers/${id}/test-connection`);
        response.data.ok ? toast.success(response.data.message || 'Connection successful') : toast.error(response.data.message || 'Connection failed');
        return;
      }

      const draftResponse = await api.post<Printer>('/printers', buildPayload());
      const createdPrinter = draftResponse.data;
      const testResponse = await api.post<PrinterConnectionTestResult>(`/printers/${createdPrinter.id}/test-connection`);
      await api.delete(`/printers/${createdPrinter.id}`);
      testResponse.data.ok ? toast.success(testResponse.data.message || 'Connection successful') : toast.error(testResponse.data.message || 'Connection failed');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Connection test failed');
    } finally {
      setTestingConnection(false);
    }
  };

  if (isEdit && isLoading) {
    return <div className="rounded-lg border border-border bg-card p-6">Loading printer...</div>;
  }

  if (isEdit && !printer) {
    return <p className="py-16 text-center text-muted-foreground">Printer not found</p>;
  }

  const selectClass = (field: string) => `flex h-9 w-full rounded-md border bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring ${errors[field] ? 'border-destructive' : 'border-input'}`;

  return (
    <div className="max-w-3xl mx-auto">
      <Link to={isEdit && id ? `/printers/${id}` : '/printers'} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4 no-underline">
        <ArrowLeft className="w-4 h-4" /> Back
      </Link>

      <div className="rounded-lg border border-border bg-card p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">Track machine details, availability, and where this printer lives.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="printer-name" required>Name</Label>
              <Input id="printer-name" value={form.name} onChange={(e) => update('name', e.target.value)} error={errors.name} placeholder="Bambu X1C #1" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="printer-slug" required>Slug</Label>
              <Input
                id="printer-slug"
                value={form.slug}
                onChange={(e) => {
                  setSlugTouched(true);
                  update('slug', slugify(e.target.value));
                }}
                error={errors.slug}
                placeholder="bambu-x1c-1"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="printer-manufacturer">Manufacturer</Label>
              <Input id="printer-manufacturer" value={form.manufacturer} onChange={(e) => update('manufacturer', e.target.value)} placeholder="Bambu Lab" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="printer-model">Model</Label>
              <Input id="printer-model" value={form.model} onChange={(e) => update('model', e.target.value)} placeholder="X1 Carbon" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="printer-serial">Serial Number</Label>
              <Input id="printer-serial" value={form.serial_number} onChange={(e) => update('serial_number', e.target.value)} placeholder="Optional" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="printer-location">Location</Label>
              <Input id="printer-location" value={form.location} onChange={(e) => update('location', e.target.value)} placeholder="Print room shelf A" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="printer-status">Status</Label>
              <select id="printer-status" value={form.status} onChange={(e) => update('status', e.target.value)} className={selectClass('status')}>
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

          <div className="rounded-lg border border-border p-4 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold">Live monitoring</h2>
                <p className="text-sm text-muted-foreground">Optional first-pass live status via provider polling. Static printers still work fine if you leave this off.</p>
              </div>
              <label className="inline-flex items-center gap-2 text-sm font-medium">
                <input type="checkbox" checked={form.monitor_enabled} onChange={(e) => update('monitor_enabled', e.target.checked)} className="h-4 w-4" />
                Enable
              </label>
            </div>

            {form.monitor_enabled ? (
              <>
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="printer-monitor-provider">Provider</Label>
                    <select id="printer-monitor-provider" value={form.monitor_provider} onChange={(e) => update('monitor_provider', e.target.value)} className={selectClass('monitor_provider')}>
                      {MONITOR_PROVIDER_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="printer-monitor-poll">Poll interval (seconds)</Label>
                    <Input id="printer-monitor-poll" type="number" min={5} max={3600} value={form.monitor_poll_interval_seconds} onChange={(e) => update('monitor_poll_interval_seconds', Number(e.target.value) || 30)} error={errors.monitor_poll_interval_seconds} />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="printer-monitor-base-url" required>Base URL</Label>
                  <Input id="printer-monitor-base-url" value={form.monitor_base_url} onChange={(e) => update('monitor_base_url', e.target.value)} error={errors.monitor_base_url} placeholder={selectedProvider.placeholder} />
                  <p className="text-xs text-muted-foreground">
                    {form.monitor_provider === 'moonraker' ? 'Use the Moonraker API URL, typically port 7125.' : 'Use the OctoPrint base URL hosting the API.'}
                  </p>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="printer-monitor-api-key">API key / token</Label>
                  <Input
                    id="printer-monitor-api-key"
                    type="password"
                    value={form.monitor_api_key}
                    onChange={(e) => {
                      update('monitor_api_key', e.target.value);
                      if (e.target.value) update('clear_monitor_api_key', false);
                    }}
                    invalid={Boolean(errors.monitor_api_key)}
                    placeholder={isEdit ? 'Enter a new key to replace the saved value' : 'Optional if your provider requires auth'}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    {printer?.monitor_api_key_configured && isEdit
                      ? 'A monitor key is already stored as a write-only secret. Leave this blank to keep it, enter a new key to replace it, or clear the saved key below.'
                      : `${selectedProvider.authHint} Stored keys are write-only and are never returned to the browser.`}
                  </p>
                  {isEdit && printer?.monitor_api_key_configured ? (
                    <label className="mt-3 inline-flex items-center gap-2 text-sm text-muted-foreground">
                      <input
                        type="checkbox"
                        checked={form.clear_monitor_api_key}
                        onChange={(e) => {
                          update('clear_monitor_api_key', e.target.checked);
                          if (e.target.checked) update('monitor_api_key', '');
                        }}
                        className="h-4 w-4"
                      />
                      Clear the saved API key on save
                    </label>
                  ) : null}
                </div>

                <div className="flex justify-end">
                  <Button type="button" variant="outline" onClick={handleTestConnection} disabled={testingConnection}>
                    <PlugZap className="h-4 w-4" />
                    {testingConnection ? 'Testing...' : 'Test connection'}
                  </Button>
                </div>
              </>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="printer-notes">Notes</Label>
            <Textarea
              id="printer-notes"
              value={form.notes}
              onChange={(e) => update('notes', e.target.value)}
              rows={5}
              placeholder="Nozzle size, preferred materials, maintenance notes, quirks, etc."
            />
          </div>

          <div className="flex gap-3 pt-2">
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Printer'}
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate(isEdit && id ? `/printers/${id}` : '/printers')}>
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
