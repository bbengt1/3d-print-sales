import { Package, Inbox, FileText, Users, Calculator, Settings, Layers, ShoppingCart } from 'lucide-react';
import type { ReactNode } from 'react';

const icons: Record<string, typeof Package> = {
  jobs: FileText,
  materials: Layers,
  rates: Calculator,
  customers: Users,
  products: Package,
  sales: ShoppingCart,
  settings: Settings,
  default: Inbox,
};

interface EmptyStateProps {
  icon?: string;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}

export default function EmptyState({ icon = 'default', title, description, action, className }: EmptyStateProps) {
  const Icon = icons[icon] || icons.default;
  return (
    <div className={`flex flex-col items-center justify-center py-16 px-4 text-center ${className || ''}`}>
      <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
        <Icon className="w-8 h-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold mb-1">{title}</h3>
      <p className="text-sm text-muted-foreground max-w-sm mb-6">{description}</p>
      {action}
    </div>
  );
}
