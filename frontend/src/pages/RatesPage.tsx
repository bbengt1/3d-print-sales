import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Edit, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
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

  const openNew = () => { setForm(emptyForm); setEditing('new'); };
  const openEdit = (r: Rate) => {
    setForm({ name: r.name, value: r.value, unit: r.unit, notes: r.notes || '' });
    setEditing(r.id);
  };
  const close = () => setEditing(null);

  const save = async () => {
    if (!form.name || !form.unit) { toast.error('Name and unit are required'); return; }
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

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Rates</h1>
        <button onClick={openNew} className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity cursor-pointer">
          <Plus className="w-4 h-4" /> Add Rate
        </button>
      </div>

      {editing !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && close()}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">{editing === 'new' ? 'Add Rate' : 'Edit Rate'}</h3>
              <button onClick={close} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div><label className="block text-sm font-medium mb-1">Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="block text-sm font-medium mb-1">Value</label><input type="number" step="0.01" value={form.value} onChange={(e) => setForm({ ...form, value: Number(e.target.value) })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
                <div><label className="block text-sm font-medium mb-1">Unit</label>
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

      {isLoading ? (
        <div className="bg-card border border-border rounded-lg p-4 h-48 animate-pulse" />
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium text-right">Value</th>
                <th className="px-4 py-3 font-medium">Unit</th>
                <th className="px-4 py-3 font-medium">Notes</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rates?.map((r) => (
                <tr key={r.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{r.name}</td>
                  <td className="px-4 py-3 text-right">{Number(r.value).toFixed(2)}</td>
                  <td className="px-4 py-3">{r.unit}</td>
                  <td className="px-4 py-3 text-muted-foreground">{r.notes || '—'}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleActive(r)} className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium cursor-pointer ${r.active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'}`}>
                      {r.active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => openEdit(r)} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground cursor-pointer" title="Edit">
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
