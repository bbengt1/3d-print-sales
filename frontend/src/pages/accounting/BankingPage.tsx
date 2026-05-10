import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Banknote, Upload, Plus, RefreshCw, ArrowRightLeft } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { getApiErrorMessage } from '@/lib/apiError';

interface BankAccount {
  id: string;
  code: string;
  name: string;
  bank_account_kind: string | null;
  current_balance: number;
}

interface Reconciliation {
  id: string;
  account_id: string;
  statement_end_date: string;
  statement_ending_balance: number;
  status: string;
}

interface Rule {
  id: string;
  name: string;
  match_field: string;
  match_pattern: string;
  category_account_id: string | null;
  active: boolean;
}

interface Transfer {
  id: string;
  from_account_id: string;
  to_account_id: string;
  amount: number;
  paid_on: string;
  received_on: string | null;
}

function AccountsTab() {
  const { data, isLoading } = useQuery<BankAccount[]>({ queryKey: ['banking-accounts'], queryFn: () => api.get('/banking/accounts').then((r) => r.data) });
  const cols: Column<BankAccount>[] = [
    { key: 'c', header: 'Code', cell: (r) => <span className="font-mono">{r.code}</span> },
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'k', header: 'Kind', cell: (r) => r.bank_account_kind || '—' },
    { key: 'b', header: 'Balance', numeric: true, cell: (r) => `$${Number(r.current_balance).toFixed(2)}` },
  ];
  return <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />;
}

function ReconciliationsTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Reconciliation[]>({ queryKey: ['reconciliations'], queryFn: () => api.get('/banking/reconciliations').then((r) => Array.isArray(r.data) ? r.data : r.data.items ?? []) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ account_id: '', statement_end_date: new Date().toISOString().slice(0, 10), statement_ending_balance: '0' });
  const save = async () => {
    try {
      await api.post('/banking/reconciliations', form);
      toast.success('Started');
      qc.invalidateQueries({ queryKey: ['reconciliations'] });
      setOpen(false);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<Reconciliation>[] = [
    { key: 'a', header: 'Account', cell: (r) => r.account_id.slice(0, 8) },
    { key: 'd', header: 'Stmt end', cell: (r) => r.statement_end_date },
    { key: 'b', header: 'Stmt balance', numeric: true, cell: (r) => `$${Number(r.statement_ending_balance).toFixed(2)}` },
    { key: 's', header: 'Status', cell: (r) => <span className="capitalize">{r.status}</span> },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />Start reconciliation</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Start reconciliation</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Account ID</Label><Input value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Statement end date</Label><Input type="date" value={form.statement_end_date} onChange={(e) => setForm({ ...form, statement_end_date: e.target.value })} /></div>
              <div><Label>Statement ending balance</Label><Input type="number" step="0.01" value={form.statement_ending_balance} onChange={(e) => setForm({ ...form, statement_ending_balance: e.target.value })} /></div>
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Start</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ImportsTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<any[]>({ queryKey: ['statement-imports'], queryFn: () => api.get('/banking/imports').then((r) => r.data) });
  const [accountId, setAccountId] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const upload = async () => {
    if (!file || !accountId) return toast.error('Account ID + CSV required');
    const fd = new FormData();
    fd.append('file', file);
    fd.append('account_id', accountId);
    try {
      await api.post('/banking/imports', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success('Imported');
      qc.invalidateQueries({ queryKey: ['statement-imports'] });
      setFile(null);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };

  const cols: Column<any>[] = [
    { key: 'd', header: 'Imported', cell: (r) => new Date(r.imported_at || r.created_at || '').toLocaleString() },
    { key: 'a', header: 'Account', cell: (r) => (r.account_id || '').slice(0, 8) },
    { key: 'n', header: 'Lines', numeric: true, cell: (r) => r.line_count ?? '—' },
    { key: 's', header: 'Status', cell: (r) => r.status || '—' },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2 rounded-lg border bg-card p-3">
        <div><Label>Account ID</Label><Input value={accountId} onChange={(e) => setAccountId(e.target.value)} /></div>
        <div><Label>CSV file</Label><Input type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
        <Button onClick={upload}><Upload className="mr-2 h-4 w-4" />Import</Button>
      </div>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
    </div>
  );
}

function RulesTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Rule[]>({ queryKey: ['statement-rules'], queryFn: () => api.get('/banking/rules').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: '', match_field: 'description', match_pattern: '', category_account_id: '' });
  const save = async () => {
    try {
      await api.post('/banking/rules', { ...form, category_account_id: form.category_account_id || null });
      toast.success('Rule created');
      qc.invalidateQueries({ queryKey: ['statement-rules'] });
      setOpen(false);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<Rule>[] = [
    { key: 'n', header: 'Name', cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: 'f', header: 'Field', cell: (r) => r.match_field },
    { key: 'p', header: 'Pattern', cell: (r) => <code>{r.match_pattern}</code> },
    { key: 'c', header: 'Category', cell: (r) => (r.category_account_id || '—').slice(0, 8) },
    { key: 'a', header: 'Active', cell: (r) => (r.active ? 'yes' : 'no') },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen(true)}><Plus className="mr-2 h-4 w-4" />New rule</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>New rule</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label>Name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Field</Label>
                <select className="mt-1 block w-full rounded-md border bg-background px-2 py-2 text-sm" value={form.match_field} onChange={(e) => setForm({ ...form, match_field: e.target.value })}>
                  <option value="description">description</option>
                  <option value="counterparty">counterparty</option>
                  <option value="memo">memo</option>
                </select>
              </div>
              <div><Label>Pattern</Label><Input value={form.match_pattern} onChange={(e) => setForm({ ...form, match_pattern: e.target.value })} placeholder="regex or substring" /></div>
            </div>
            <div><Label>Category account ID</Label><Input value={form.category_account_id} onChange={(e) => setForm({ ...form, category_account_id: e.target.value })} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TransfersTab() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<Transfer[]>({ queryKey: ['inter-account-transfers'], queryFn: () => api.get('/banking/inter-account-transfers').then((r) => r.data) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ from_account_id: '', to_account_id: '', amount: '0', paid_on: new Date().toISOString().slice(0, 10) });
  const save = async () => {
    try {
      await api.post('/banking/inter-account-transfers', form);
      toast.success('Transfer recorded');
      qc.invalidateQueries({ queryKey: ['inter-account-transfers'] });
      setOpen(false);
    } catch (err) { toast.error(getApiErrorMessage(err, 'Failed')); }
  };
  const cols: Column<Transfer>[] = [
    { key: 'd', header: 'Paid on', cell: (r) => r.paid_on },
    { key: 'f', header: 'From', cell: (r) => r.from_account_id.slice(0, 8) },
    { key: 't', header: 'To', cell: (r) => r.to_account_id.slice(0, 8) },
    { key: 'a', header: 'Amount', numeric: true, cell: (r) => `$${Number(r.amount).toFixed(2)}` },
    { key: 'r', header: 'Received', cell: (r) => r.received_on || '—' },
  ];
  return (
    <div className="space-y-3">
      <Button onClick={() => setOpen(true)}><ArrowRightLeft className="mr-2 h-4 w-4" />New transfer</Button>
      <DataTable data={data ?? []} columns={cols} rowKey={(r) => r.id} loading={isLoading} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Inter-account transfer</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><Label>From account ID</Label><Input value={form.from_account_id} onChange={(e) => setForm({ ...form, from_account_id: e.target.value })} /></div>
              <div><Label>To account ID</Label><Input value={form.to_account_id} onChange={(e) => setForm({ ...form, to_account_id: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Amount</Label><Input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></div>
              <div><Label>Paid on</Label><Input type="date" value={form.paid_on} onChange={(e) => setForm({ ...form, paid_on: e.target.value })} /></div>
            </div>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={save}>Create</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function BankingPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Banking" description="Bank accounts, reconciliation, statement import, match rules, transfers" />
      <Tabs defaultValue="accounts">
        <TabsList>
          <TabsTrigger value="accounts"><Banknote className="mr-2 h-4 w-4" />Accounts</TabsTrigger>
          <TabsTrigger value="reconciliations"><RefreshCw className="mr-2 h-4 w-4" />Reconciliations</TabsTrigger>
          <TabsTrigger value="imports"><Upload className="mr-2 h-4 w-4" />Imports</TabsTrigger>
          <TabsTrigger value="rules">Rules</TabsTrigger>
          <TabsTrigger value="transfers"><ArrowRightLeft className="mr-2 h-4 w-4" />Transfers</TabsTrigger>
        </TabsList>
        <TabsContent value="accounts" className="mt-4"><AccountsTab /></TabsContent>
        <TabsContent value="reconciliations" className="mt-4"><ReconciliationsTab /></TabsContent>
        <TabsContent value="imports" className="mt-4"><ImportsTab /></TabsContent>
        <TabsContent value="rules" className="mt-4"><RulesTab /></TabsContent>
        <TabsContent value="transfers" className="mt-4"><TransfersTab /></TabsContent>
      </Tabs>
    </div>
  );
}
