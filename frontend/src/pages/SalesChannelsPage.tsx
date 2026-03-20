import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Edit, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { SkeletonTable } from '@/components/ui/Skeleton';
import EmptyState from '@/components/ui/EmptyState';
import type { SalesChannel } from '@/types';

const emptyForm = { name: '', platform_fee_pct: 0, fixed_fee: 0, is_active: true };

export default function SalesChannelsPage() {
  const queryClient = useQueryClient();
  const { data: channels, isLoading } = useQuery<SalesChannel[]>({
    queryKey: ['sales-channels'],
    queryFn: () => api.get('/sales/channels').then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const openNew = () => { setForm(emptyForm); setEditing('new'); };
  const openEdit = (ch: SalesChannel) => {
    setForm({
      name: ch.name,
      platform_fee_pct: Number(ch.platform_fee_pct),
      fixed_fee: Number(ch.fixed_fee),
      is_active: ch.is_active,
    });
    setEditing(ch.id);
  };
  const close = () => setEditing(null);

  const save = async () => {
    if (!form.name.trim()) { toast.error('Name is required'); return; }
    setSaving(true);
    try {
      if (editing === 'new') {
        await api.post('/sales/channels', form);
        toast.success('Channel created');
      } else {
        await api.put(`/sales/channels/${editing}`, form);
        toast.success('Channel updated');
      }
      queryClient.invalidateQueries({ queryKey: ['sales-channels'] });
      close();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (ch: SalesChannel) => {
    try {
      if (ch.is_active) {
        await api.delete(`/sales/channels/${ch.id}`);
        toast.success(`${ch.name} deactivated`);
      } else {
        await api.put(`/sales/channels/${ch.id}`, { is_active: true });
        toast.success(`${ch.name} activated`);
      }
      queryClient.invalidateQueries({ queryKey: ['sales-channels'] });
    } catch {
      toast.error('Failed to update');
    }
  };

  const inputCls = 'w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring';

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Sales Channels</h1>
        <button onClick={openNew} className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity cursor-pointer">
          <Plus className="w-4 h-4" /> Add Channel
        </button>
      </div>

      {/* Modal */}
      {editing !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && close()}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">{editing === 'new' ? 'Add Channel' : 'Edit Channel'}</h3>
              <button onClick={close} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Name *</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputCls} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Platform Fee %</label>
                  <input type="number" step="0.1" min="0" max="100" value={form.platform_fee_pct} onChange={(e) => setForm({ ...form, platform_fee_pct: Number(e.target.value) })} className={inputCls} />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Fixed Fee ($)</label>
                  <input type="number" step="0.01" min="0" value={form.fixed_fee} onChange={(e) => setForm({ ...form, fixed_fee: Number(e.target.value) })} className={inputCls} />
                </div>
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
        <SkeletonTable rows={4} cols={5} />
      ) : !channels?.length ? (
        <EmptyState
          icon="default"
          title="No sales channels"
          description="Add a sales channel to track platform fees."
          action={
            <button onClick={openNew} className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 cursor-pointer">
              <Plus className="w-4 h-4" /> Add Channel
            </button>
          }
        />
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium text-right">Platform Fee %</th>
                <th className="px-4 py-3 font-medium text-right">Fixed Fee</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {channels.map((ch) => (
                <tr key={ch.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{ch.name}</td>
                  <td className="px-4 py-3 text-right">{Number(ch.platform_fee_pct).toFixed(1)}%</td>
                  <td className="px-4 py-3 text-right">${Number(ch.fixed_fee).toFixed(2)}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleActive(ch)} className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium cursor-pointer ${ch.is_active ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'}`}>
                      {ch.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => openEdit(ch)} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground cursor-pointer" title="Edit">
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
