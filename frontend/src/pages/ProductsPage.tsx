import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Plus, Edit, X, Eye, AlertTriangle, ArchiveRestore, Archive } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import { SkeletonTable } from '@/components/ui/Skeleton';
import EmptyState from '@/components/ui/EmptyState';
import type { Product, PaginatedProducts, Material } from '@/types';

const emptyForm = {
  name: '',
  description: '',
  material_id: '',
  upc: '',
  unit_price: 0,
  reorder_point: 5,
};

export default function ProductsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const limit = 25;

  const { data, isLoading } = useQuery<PaginatedProducts>({
    queryKey: ['products', search, page],
    queryFn: () =>
      api.get('/products', { params: { search: search || undefined, skip: page * limit, limit } }).then((r) => r.data),
  });

  const { data: materials } = useQuery<Material[]>({
    queryKey: ['materials', 'active'],
    queryFn: () => api.get('/materials?active=true').then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const openNew = () => { setForm(emptyForm); setFormErrors({}); setEditing('new'); };
  const openEdit = (p: Product) => {
    setForm({
      name: p.name,
      description: p.description || '',
      material_id: p.material_id,
      upc: p.upc || '',
      unit_price: Number(p.unit_price),
      reorder_point: p.reorder_point,
    });
    setFormErrors({});
    setEditing(p.id);
  };
  const close = () => setEditing(null);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = 'Name is required';
    if (!form.material_id) errs.material_id = 'Select a material';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const save = async () => {
    if (!validate()) return;
    setSaving(true);
    try {
      const payload = {
        ...form,
        description: form.description || null,
        upc: form.upc || null,
      };
      if (editing === 'new') {
        await api.post('/products', payload);
        toast.success('Product created');
      } else {
        await api.put(`/products/${editing}`, payload);
        toast.success('Product updated');
      }
      queryClient.invalidateQueries({ queryKey: ['products'] });
      close();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (p: Product) => {
    const action = p.is_active ? 'archive' : 'restore';
    const confirmed = window.confirm(
      p.is_active
        ? `Archive ${p.name}?\n\nThis will remove it from active use but keep historical records and inventory history.`
        : `Restore ${p.name} to active products?`
    );

    if (!confirmed) return;

    try {
      if (p.is_active) {
        await api.delete(`/products/${p.id}`);
        toast.success(`${p.name} archived`);
      } else {
        await api.put(`/products/${p.id}`, { is_active: true });
        toast.success(`${p.name} restored`);
      }
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', p.id] });
    } catch {
      toast.error(`Failed to ${action} product`);
    }
  };

  const products = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  const inputCls = (field: string) =>
    `w-full px-3 py-2 border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring ${formErrors[field] ? 'border-destructive' : 'border-input'}`;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Products</h1>
        <button onClick={openNew} className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity cursor-pointer">
          <Plus className="w-4 h-4" /> Add Product
        </button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <input
          placeholder="Search products by name or SKU..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          className="w-full max-w-md px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Modal */}
      {editing !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && close()}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">{editing === 'new' ? 'Add Product' : 'Edit Product'}</h3>
              <button onClick={close} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Name *</label>
                <input value={form.name} onChange={(e) => { setForm({ ...form, name: e.target.value }); setFormErrors({ ...formErrors, name: '' }); }} className={inputCls('name')} />
                {formErrors.name && <p className="text-destructive text-xs mt-1">{formErrors.name}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Material *</label>
                <select
                  value={form.material_id}
                  onChange={(e) => { setForm({ ...form, material_id: e.target.value }); setFormErrors({ ...formErrors, material_id: '' }); }}
                  className={inputCls('material_id')}
                >
                  <option value="">Select material...</option>
                  {materials?.map((m) => (
                    <option key={m.id} value={m.id}>{m.name} ({m.brand})</option>
                  ))}
                </select>
                {formErrors.material_id && <p className="text-destructive text-xs mt-1">{formErrors.material_id}</p>}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Unit Price ($)</label>
                  <input type="number" step="0.01" min="0" value={form.unit_price} onChange={(e) => setForm({ ...form, unit_price: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Reorder Point</label>
                  <input type="number" min="0" value={form.reorder_point} onChange={(e) => setForm({ ...form, reorder_point: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">UPC/EAN (optional)</label>
                <input value={form.upc} onChange={(e) => setForm({ ...form, upc: e.target.value })} placeholder="012345678901" className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={save} disabled={saving} className="flex-1 bg-primary text-primary-foreground py-2 rounded-md font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer">{saving ? 'Saving...' : 'Save'}</button>
              <button onClick={close} className="px-4 py-2 border border-border rounded-md hover:bg-accent cursor-pointer">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <SkeletonTable rows={5} cols={8} />
      ) : !products.length ? (
        <EmptyState
          icon="default"
          title="No products yet"
          description="Add your first product to start tracking inventory."
          action={
            <button onClick={openNew} className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 cursor-pointer">
              <Plus className="w-4 h-4" /> Add Product
            </button>
          }
        />
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto bg-card border border-border rounded-lg">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-3 font-medium">SKU</th>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium text-right">Price</th>
                  <th className="px-4 py-3 font-medium text-right">Cost</th>
                  <th className="px-4 py-3 font-medium text-right">Stock</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                    <td className="px-4 py-3 font-mono text-xs">{p.sku}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{p.name}</div>
                      {!p.is_active && <div className="text-xs text-muted-foreground mt-0.5">Archived product</div>}
                    </td>
                    <td className="px-4 py-3 text-right">{formatCurrency(p.unit_price)}</td>
                    <td className="px-4 py-3 text-right">{formatCurrency(p.unit_cost)}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`inline-flex items-center gap-1 ${p.stock_qty <= p.reorder_point ? 'text-amber-600 dark:text-amber-400' : ''}`}>
                        {p.stock_qty <= p.reorder_point && <AlertTriangle className="w-3 h-3" />}
                        {p.stock_qty}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${p.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'}`}>
                        {p.is_active ? 'Active' : 'Archived'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        <Link to={`/products/${p.id}`} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground" title="View">
                          <Eye className="w-4 h-4" />
                        </Link>
                        <button onClick={() => openEdit(p)} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground cursor-pointer" title="Edit">
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => toggleActive(p)}
                          className="p-1.5 hover:bg-accent rounded-md text-muted-foreground cursor-pointer"
                          title={p.is_active ? 'Archive product' : 'Restore product'}
                        >
                          {p.is_active ? <Archive className="w-4 h-4" /> : <ArchiveRestore className="w-4 h-4" />}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {products.map((p) => (
              <Link key={p.id} to={`/products/${p.id}`} className="block bg-card border border-border rounded-lg p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-semibold">{p.name}</p>
                    <p className="text-xs text-muted-foreground font-mono">{p.sku}</p>
                    {!p.is_active && <p className="text-xs text-muted-foreground mt-1">Archived product</p>}
                  </div>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${p.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'}`}>
                    {p.is_active ? 'Active' : 'Archived'}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div><p className="text-xs text-muted-foreground">Price</p><p>{formatCurrency(p.unit_price)}</p></div>
                  <div><p className="text-xs text-muted-foreground">Cost</p><p>{formatCurrency(p.unit_cost)}</p></div>
                  <div>
                    <p className="text-xs text-muted-foreground">Stock</p>
                    <p className={p.stock_qty <= p.reorder_point ? 'text-amber-600 dark:text-amber-400' : ''}>
                      {p.stock_qty <= p.reorder_point && '⚠ '}{p.stock_qty}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-muted-foreground">{total} products</p>
              <div className="flex gap-2">
                <button disabled={page === 0} onClick={() => setPage(page - 1)} className="px-3 py-1 border border-border rounded-md text-sm hover:bg-accent disabled:opacity-50 cursor-pointer">Prev</button>
                <span className="px-3 py-1 text-sm">{page + 1} / {totalPages}</span>
                <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)} className="px-3 py-1 border border-border rounded-md text-sm hover:bg-accent disabled:opacity-50 cursor-pointer">Next</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
