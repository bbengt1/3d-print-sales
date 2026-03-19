import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Edit, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import type { Material } from '@/types';

const emptyForm = { name: '', brand: '', spool_weight_g: 1000, spool_price: 20, net_usable_g: 950, notes: '' };

export default function MaterialsPage() {
  const queryClient = useQueryClient();
  const { data: materials, isLoading } = useQuery<Material[]>({
    queryKey: ['materials'],
    queryFn: () => api.get('/materials').then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const openNew = () => { setForm(emptyForm); setEditing('new'); };
  const openEdit = (m: Material) => {
    setForm({ name: m.name, brand: m.brand, spool_weight_g: m.spool_weight_g, spool_price: m.spool_price, net_usable_g: m.net_usable_g, notes: m.notes || '' });
    setEditing(m.id);
  };
  const close = () => { setEditing(null); };

  const save = async () => {
    if (!form.name || !form.brand) { toast.error('Name and brand are required'); return; }
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

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Materials</h1>
        <button onClick={openNew} className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity cursor-pointer">
          <Plus className="w-4 h-4" /> Add Material
        </button>
      </div>

      {/* Modal */}
      {editing !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && close()}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">{editing === 'new' ? 'Add Material' : 'Edit Material'}</h3>
              <button onClick={close} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div><label className="block text-sm font-medium mb-1">Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
              <div><label className="block text-sm font-medium mb-1">Brand</label><input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
              <div className="grid grid-cols-3 gap-3">
                <div><label className="block text-sm font-medium mb-1">Spool (g)</label><input type="number" value={form.spool_weight_g} onChange={(e) => setForm({ ...form, spool_weight_g: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
                <div><label className="block text-sm font-medium mb-1">Price ($)</label><input type="number" step="0.01" value={form.spool_price} onChange={(e) => setForm({ ...form, spool_price: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
                <div><label className="block text-sm font-medium mb-1">Usable (g)</label><input type="number" value={form.net_usable_g} onChange={(e) => setForm({ ...form, net_usable_g: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
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

      {isLoading ? (
        <div className="bg-card border border-border rounded-lg p-4 h-48 animate-pulse" />
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Brand</th>
                <th className="px-4 py-3 font-medium text-right">Spool (g)</th>
                <th className="px-4 py-3 font-medium text-right">Price</th>
                <th className="px-4 py-3 font-medium text-right">Usable (g)</th>
                <th className="px-4 py-3 font-medium text-right">Cost/g</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {materials?.map((m) => (
                <tr key={m.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{m.name}</td>
                  <td className="px-4 py-3">{m.brand}</td>
                  <td className="px-4 py-3 text-right">{m.spool_weight_g}</td>
                  <td className="px-4 py-3 text-right">{formatCurrency(m.spool_price)}</td>
                  <td className="px-4 py-3 text-right">{m.net_usable_g}</td>
                  <td className="px-4 py-3 text-right">${Number(m.cost_per_g).toFixed(4)}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleActive(m)} className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium cursor-pointer ${m.active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'}`}>
                      {m.active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => openEdit(m)} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground cursor-pointer" title="Edit">
                      <Edit className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
