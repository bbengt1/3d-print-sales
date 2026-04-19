import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import StatusBadge from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import type { Material } from '@/types';

const emptyForm = { name: '', brand: '', spool_weight_g: 1000, spool_price: 20, net_usable_g: 950, notes: '', spools_in_stock: 0, reorder_point: 2 };

export default function MaterialsPage() {
  const queryClient = useQueryClient();
  const { data: materials, isLoading } = useQuery<Material[]>({
    queryKey: ['materials'],
    queryFn: () => api.get('/materials').then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const openNew = () => { setForm(emptyForm); setFormErrors({}); setEditing('new'); };
  const openEdit = (m: Material) => {
    setForm({ name: m.name, brand: m.brand, spool_weight_g: m.spool_weight_g, spool_price: m.spool_price, net_usable_g: m.net_usable_g, notes: m.notes || '', spools_in_stock: m.spools_in_stock, reorder_point: m.reorder_point });
    setFormErrors({});
    setEditing(m.id);
  };
  const close = () => { setEditing(null); };

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = 'Name is required';
    if (!form.brand.trim()) errs.brand = 'Brand is required';
    if (form.spool_weight_g <= 0) errs.spool_weight_g = 'Must be > 0';
    if (form.spool_price <= 0) errs.spool_price = 'Must be > 0';
    if (form.net_usable_g <= 0) errs.net_usable_g = 'Must be > 0';
    if (form.net_usable_g > form.spool_weight_g) errs.net_usable_g = 'Cannot exceed spool weight';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const save = async () => {
    if (!validate()) return;
    setSaving(true);
    try {
      if (editing === 'new') {
        await api.post('/materials', form);
        toast.success('Material created');
      } else {
        await api.put(`/materials/${editing}`, form);
        toast.success('Material updated');
      }
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      close();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const toggleActive = async (m: Material) => {
    try {
      if (m.active) {
        await api.delete(`/materials/${m.id}`);
        toast.success(`${m.name} deactivated`);
      } else {
        await api.put(`/materials/${m.id}`, { active: true });
        toast.success(`${m.name} activated`);
      }
      queryClient.invalidateQueries({ queryKey: ['materials'] });
    } catch { toast.error('Failed to update'); }
  };

  const inputCls = (field: string) =>
    `w-full px-3 py-2 border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring ${formErrors[field] ? 'border-destructive' : 'border-input'}`;

  const columns: Column<Material>[] = [
    { key: 'name', header: 'Name', cell: (m) => <span className="font-medium">{m.name}</span> },
    { key: 'brand', header: 'Brand', cell: (m) => m.brand },
    { key: 'spool_weight_g', header: 'Spool (g)', numeric: true, cell: (m) => m.spool_weight_g },
    { key: 'spool_price', header: 'Price', numeric: true, cell: (m) => formatCurrency(m.spool_price) },
    {
      key: 'net_usable_g',
      header: 'Usable (g)',
      numeric: true,
      colClassName: 'hidden lg:table-cell',
      cell: (m) => m.net_usable_g,
    },
    {
      key: 'cost_per_g',
      header: 'Cost/g',
      numeric: true,
      cell: (m) => `$${Number(m.cost_per_g).toFixed(4)}`,
    },
    {
      key: 'spools_in_stock',
      header: 'Spools',
      numeric: true,
      cell: (m) => (
        <span className={m.spools_in_stock <= m.reorder_point ? 'text-amber-600 dark:text-amber-400 font-medium' : ''}>
          {m.spools_in_stock}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      cell: (m) => (
        <button
          type="button"
          onClick={() => toggleActive(m)}
          aria-label={m.active ? `Deactivate ${m.name}` : `Activate ${m.name}`}
          className="cursor-pointer"
        >
          <StatusBadge tone={m.active ? 'success' : 'destructive'}>
            {m.active ? 'Active' : 'Inactive'}
          </StatusBadge>
        </button>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '48px',
      cell: (m) => (
        <button
          type="button"
          onClick={() => openEdit(m)}
          aria-label={`Edit ${m.name}`}
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Edit className="h-4 w-4" />
        </button>
      ),
    },
  ];

  const total = materials?.length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Materials"
        description={`${total.toLocaleString()} ${total === 1 ? 'material' : 'materials'}`}
        actions={
          <button
            type="button"
            onClick={openNew}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" /> Add material
          </button>
        }
      />

      {/* Modal */}
      {editing !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && close()}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">{editing === 'new' ? 'Add Material' : 'Edit Material'}</h3>
              <button onClick={close} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Name *</label>
                <input value={form.name} onChange={(e) => { setForm({ ...form, name: e.target.value }); setFormErrors({ ...formErrors, name: '' }); }} className={inputCls('name')} />
                {formErrors.name && <p className="text-destructive text-xs mt-1">{formErrors.name}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Brand *</label>
                <input value={form.brand} onChange={(e) => { setForm({ ...form, brand: e.target.value }); setFormErrors({ ...formErrors, brand: '' }); }} className={inputCls('brand')} />
                {formErrors.brand && <p className="text-destructive text-xs mt-1">{formErrors.brand}</p>}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Spool (g) *</label>
                  <input type="number" value={form.spool_weight_g} onChange={(e) => setForm({ ...form, spool_weight_g: Number(e.target.value) })} className={inputCls('spool_weight_g')} />
                  {formErrors.spool_weight_g && <p className="text-destructive text-xs mt-1">{formErrors.spool_weight_g}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Price ($) *</label>
                  <input type="number" step="0.01" value={form.spool_price} onChange={(e) => setForm({ ...form, spool_price: Number(e.target.value) })} className={inputCls('spool_price')} />
                  {formErrors.spool_price && <p className="text-destructive text-xs mt-1">{formErrors.spool_price}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Usable (g) *</label>
                  <input type="number" value={form.net_usable_g} onChange={(e) => setForm({ ...form, net_usable_g: Number(e.target.value) })} className={inputCls('net_usable_g')} />
                  {formErrors.net_usable_g && <p className="text-destructive text-xs mt-1">{formErrors.net_usable_g}</p>}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Spools in Stock</label>
                  <input type="number" min="0" value={form.spools_in_stock} onChange={(e) => setForm({ ...form, spools_in_stock: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Reorder Point</label>
                  <input type="number" min="0" value={form.reorder_point} onChange={(e) => setForm({ ...form, reorder_point: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
                </div>
              </div>
              <div><label className="block text-sm font-medium mb-1">Notes</label><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
              {form.net_usable_g > 0 && (
                <p className="text-sm text-muted-foreground">Cost/g: ${(form.spool_price / form.net_usable_g).toFixed(4)}</p>
              )}
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={save} disabled={saving} className="flex-1 bg-primary text-primary-foreground py-2 rounded-md font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer">{saving ? 'Saving...' : 'Save'}</button>
              <button onClick={close} className="px-4 py-2 border border-border rounded-md hover:bg-accent cursor-pointer">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop table */}
      <div className="hidden md:block">
        <DataTable<Material>
          data={materials || []}
          columns={columns}
          rowKey={(m) => m.id}
          loading={isLoading}
          emptyState="No materials yet — add your first filament to start tracking costs."
          toolbar={<TableToolbar total={total} />}
        />
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3">
        {materials?.map((m) => (
          <div key={m.id} className="rounded-md border border-border bg-card p-4">
            <div className="mb-2 flex items-start justify-between">
              <div>
                <p className="font-semibold">{m.name}</p>
                <p className="text-xs text-muted-foreground">{m.brand}</p>
              </div>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => toggleActive(m)}>
                  <StatusBadge tone={m.active ? 'success' : 'destructive'}>{m.active ? 'Active' : 'Inactive'}</StatusBadge>
                </button>
                <button
                  type="button"
                  onClick={() => openEdit(m)}
                  aria-label={`Edit ${m.name}`}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"
                >
                  <Edit className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Spool</p>
                <p className="tabular-nums">{m.spool_weight_g}g</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Price</p>
                <p className="tabular-nums">{formatCurrency(m.spool_price)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Cost/g</p>
                <p className="tabular-nums">${Number(m.cost_per_g).toFixed(4)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
