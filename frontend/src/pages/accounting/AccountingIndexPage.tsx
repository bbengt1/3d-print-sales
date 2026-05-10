import { Link } from 'react-router-dom';
import {
  Banknote, Building2, ClipboardList, CreditCard, FileMinus, FileText,
  Layers, MapPin, Receipt, RefreshCw, Repeat, ScrollText, Truck, Wallet,
  type LucideIcon,
} from 'lucide-react';
import PageHeader from '@/components/layout/PageHeader';

interface Tile { to: string; label: string; icon: LucideIcon; description: string }

const tiles: Tile[] = [
  { to: '/accounting/invoices', label: 'Invoices', icon: FileText, description: 'Customer invoices, payments, email send' },
  { to: '/accounting/quotes', label: 'Quotes', icon: ScrollText, description: 'Customer quotes, accept, convert' },
  { to: '/accounting/sales-orders', label: 'Sales orders', icon: ClipboardList, description: 'Confirm, then convert to invoice' },
  { to: '/accounting/purchase-orders', label: 'Purchase orders', icon: ClipboardList, description: 'Confirm, then convert to bill' },
  { to: '/accounting/delivery-notes', label: 'Delivery notes', icon: Truck, description: 'Dispatch documents (DLV-…)' },
  { to: '/accounting/credit-notes', label: 'Credit notes', icon: FileMinus, description: 'Refunds applied to invoices' },
  { to: '/accounting/debit-notes', label: 'Debit notes', icon: FileMinus, description: 'Vendor returns applied to bills' },
  { to: '/accounting/recurring-invoices', label: 'Recurring invoices', icon: Repeat, description: 'Auto-generate on a schedule' },
  { to: '/accounting/banking', label: 'Banking', icon: Banknote, description: 'Reconciliation, imports, rules, transfers' },
  { to: '/accounting/expense-claims', label: 'Expense claims', icon: Wallet, description: 'Owner-paid reimbursable expenses' },
  { to: '/accounting/fixed-assets', label: 'Fixed assets', icon: Building2, description: 'Depreciation schedule' },
  { to: '/accounting/intangibles', label: 'Intangibles', icon: Layers, description: 'Amortization schedule' },
  { to: '/accounting/production-orders', label: 'Production orders', icon: RefreshCw, description: 'FIFO consume + finished-goods layers' },
  { to: '/accounting/locations', label: 'Locations & kits', icon: MapPin, description: 'Multi-location inventory + transfers + kits' },
  { to: '/accounting/reports', label: 'Reports', icon: Receipt, description: 'Trial balance · Receipts/payments · Aging' },
  { to: '/accounting/foundations', label: 'Foundations', icon: CreditCard, description: 'Recurring JEs · Suspense · Starting balances' },
  { to: '/accounting/master-data', label: 'Master data', icon: ClipboardList, description: 'Divisions · Projects · Budgets · Custom fields · Batch' },
  { to: '/accounting/tax-profiles', label: 'Tax profiles', icon: Receipt, description: 'Compound + reverse-charge tax profiles' },
];

export default function AccountingIndexPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Accounting" description="Manager.io-style finance suite — pick a module to start" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map(({ to, label, icon: Icon, description }) => (
          <Link key={to} to={to} className="group rounded-lg border bg-card p-4 no-underline transition-colors hover:bg-accent">
            <div className="mb-2 flex items-center gap-2 text-foreground">
              <Icon className="h-5 w-5 text-primary" />
              <span className="font-medium">{label}</span>
            </div>
            <p className="text-sm text-muted-foreground">{description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
