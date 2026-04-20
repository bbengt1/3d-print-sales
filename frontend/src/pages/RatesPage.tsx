import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import StatusBadge from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import type { Rate } from '@/types';

const emptyForm = { name: '', value: 0, unit: '$/hour', notes: '' };

export default function RatesPage() {
  const queryClient = useQueryClient();
  const { data: rates, isLoading } = useQuery<Rate[]>({
    queryKey: ['rates'],
    queryFn: () => api.get('/rates').then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const openNew = () => { setForm(emptyForm); setFormErrors({}); setEditing('new'); };
  const openEdit = (r: Rate) => {
    setForm({ name: r.name, value: r.value, unit: r.unit, notes: r.notes || '' });
    setFormErrors({});
    setEditing(r.id);
  };
  const close = () => setEditing(null);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = 'Name is required';
    if (form.value < 0) errs.value = 'Must be >= 0';
    if (!form.unit) errs.unit = 'Unit is required';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const save = async () => {
    if (!validate()) return;
    setSaving(true);
    try {
      if (editing === 'new') {
        await api.post('/rates', form);
        toast.success('Rate created');
      } else {
        await api.put(`/rates/${editing}`, form);
        toast.success('Rate updated');
      }
      queryClient.invalidateQueries({ queryKey: ['rates'] });
      close();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const toggleActive = async (r: Rate) => {
    try {
      if (r.active) {
        await api.delete(`/rates/${r.id}`);
        toast.success(`${r.name} deactivated`);
      } else {
        await api.put(`/rates/${r.id}`, { active: true });
        toast.success(`${r.name} activated`);
      }
      queryClient.invalidateQueries({ queryKey: ['rates'] });
    } catch { toast.error('Failed to update'); }
  };

  const columns: Column<Rate>[] = [
    { key: 'name', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'value', header: 'Value', numeric: true, cell: (r) => Number(r.value).toFixed(2) },
    { key: 'unit', header: 'Unit', cell: (r) => r.unit },
    {
      key: 'notes',
      header: 'Notes',
      colClassName: 'hidden lg:table-cell',
      cell: (r) => r.notes || <span className="text-muted-foreground">—</span>,
    },
    {
      key: 'status',
      header: 'Status',
      cell: (r) => (
        <button
          type="button"
          onClick={() => toggleActive(r)}
          aria-label={r.active ? `Deactivate ${r.name}` : `Activate ${r.name}`}
          className="cursor-pointer"
        >
          <StatusBadge tone={r.active ? 'success' : 'destructive'}>
            {r.active ? 'Active' : 'Inactive'}
          </StatusBadge>
        </button>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '48px',
      cell: (r) => (
        <button
          type="button"
          onClick={() => openEdit(r)}
          aria-label={`Edit ${r.name}`}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Edit className="h-4 w-4" />
        </button>
      ),
    },
  ];

  const total = rates?.length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rates"
        description={`${total.toLocaleString()} ${total === 1 ? 'rate' : 'rates'}`}
        actions={
          <Button type="button" onClick={openNew}>
            <Plus className="h-4 w-4" /> Add rate
          </Button>
        }
      />

      <Dialog open={editing !== null} onOpenChange={(o) => !o && close()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing === 'new' ? 'Add rate' : 'Edit rate'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="rate-name">Name *</Label>
              <Input
                id="rate-name"
                value={form.name}
                onChange={(e) => {
                  setForm({ ...form, name: e.target.value });
                  setFormErrors({ ...formErrors, name: '' });
                }}
                invalid={Boolean(formErrors.name)}
              />
              {formErrors.name && <p className="text-destructive text-xs">{formErrors.name}</p>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="rate-value">Value *</Label>
                <Input
                  id="rate-value"
                  type="number"
                  step="0.01"
                  value={form.value}
                  onChange={(e) => setForm({ ...form, value: Number(e.target.value) })}
                  invalid={Boolean(formErrors.value)}
                />
                {formErrors.value && <p className="text-destructive text-xs">{formErrors.value}</p>}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rate-unit">Unit *</Label>
                <select
                  id="rate-unit"
                  value={form.unit}
                  onChange={(e) => setForm({ ...form, unit: e.target.value })}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="$/hour">$/hour</option>
                  <option value="$/order">$/order</option>
                  <option value="%">%</option>
                </select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="rate-notes">Notes</Label>
              <Input id="rate-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={close}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="hidden md:block">
        <DataTable<Rate>
          data={rates || []}
          columns={columns}
          rowKey={(r) => r.id}
          loading={isLoading}
          emptyState="No rates configured. Add labor, machine, and overhead rates to enable cost calculations."
          toolbar={<TableToolbar total={total} />}
        />
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3">
        {rates?.map((r) => (
          <div key={r.id} className="rounded-md border border-border bg-card p-4">
            <div className="mb-2 flex items-start justify-between">
              <div>
                <p className="font-semibold">{r.name}</p>
                {r.notes && <p className="text-xs text-muted-foreground">{r.notes}</p>}
              </div>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => toggleActive(r)}>
                  <StatusBadge tone={r.active ? 'success' : 'destructive'}>{r.active ? 'Active' : 'Inactive'}</StatusBadge>
                </button>
                <button
                  type="button"
                  onClick={() => openEdit(r)}
                  aria-label={`Edit ${r.name}`}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"
                >
                  <Edit className="h-4 w-4" />
                </button>
              </div>
            </div>
            <p className="text-lg font-semibold tabular-nums">
              {Number(r.value).toFixed(2)}
              <span className="ml-1 text-sm font-normal text-muted-foreground">{r.unit}</span>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
