import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import StatusBadge from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
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

  const inputCls = (field: string) =>
    `w-full px-3 py-2 border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring ${formErrors[field] ? 'border-destructive' : 'border-input'}`;

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
          <button
            type="button"
            onClick={openNew}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" /> Add rate
          </button>
        }
      />

      {editing !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && close()}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">{editing === 'new' ? 'Add Rate' : 'Edit Rate'}</h3>
              <button onClick={close} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Name *</label>
                <input value={form.name} onChange={(e) => { setForm({ ...form, name: e.target.value }); setFormErrors({ ...formErrors, name: '' }); }} className={inputCls('name')} />
                {formErrors.name && <p className="text-destructive text-xs mt-1">{formErrors.name}</p>}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Value *</label>
                  <input type="number" step="0.01" value={form.value} onChange={(e) => setForm({ ...form, value: Number(e.target.value) })} className={inputCls('value')} />
                  {formErrors.value && <p className="text-destructive text-xs mt-1">{formErrors.value}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Unit *</label>
                  <select value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring">
                    <option value="$/hour">$/hour</option>
                    <option value="$/order">$/order</option>
                    <option value="%">%</option>
                  </select>
                </div>
              </div>
              <div><label className="block text-sm font-medium mb-1">Notes</label><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={save} disabled={saving} className="flex-1 bg-primary text-primary-foreground py-2 rounded-md font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer">{saving ? 'Saving...' : 'Save'}</button>
              <button onClick={close} className="px-4 py-2 border border-border rounded-md hover:bg-accent cursor-pointer">Cancel</button>
            </div>
          </div>
        </div>
      )}

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
