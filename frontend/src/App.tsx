import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import Layout from '@/components/layout/Layout';
import AdminLayout from '@/components/layout/AdminLayout';
import ProtectedRoute from '@/components/auth/ProtectedRoute';
import DashboardPage from '@/pages/DashboardPage';
import JobsPage from '@/pages/JobsPage';
import JobDetailPage from '@/pages/JobDetailPage';
import JobFormPage from '@/pages/JobFormPage';
import MaterialsPage from '@/pages/MaterialsPage';
import RatesPage from '@/pages/RatesPage';
import CustomersPage from '@/pages/CustomersPage';
import ProductsPage from '@/pages/ProductsPage';
import ProductDetailPage from '@/pages/ProductDetailPage';
import PrintersPage from '@/pages/PrintersPage';
import PrinterDetailPage from '@/pages/PrinterDetailPage';
import PrinterFormPage from '@/pages/PrinterFormPage';
import InventoryPage from '@/pages/InventoryPage';
import SalesPage from '@/pages/SalesPage';
import SaleDetailPage from '@/pages/SaleDetailPage';
import SaleFormPage from '@/pages/SaleFormPage';
import SalesChannelsPage from '@/pages/SalesChannelsPage';
import CalculatorPage from '@/pages/CalculatorPage';
import ReportsLayout from '@/pages/reports/ReportsLayout';
import InventoryReportPage from '@/pages/reports/InventoryReportPage';
import SalesReportPage from '@/pages/reports/SalesReportPage';
import PLReportPage from '@/pages/reports/PLReportPage';
import LoginPage from '@/pages/LoginPage';
import SettingsPage from '@/pages/admin/SettingsPage';
import UsersPage from '@/pages/admin/UsersPage';
import DataPage from '@/pages/admin/DataPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<DashboardPage />} />
              <Route path="/jobs" element={<JobsPage />} />
              <Route path="/jobs/new" element={<JobFormPage />} />
              <Route path="/jobs/:id" element={<JobDetailPage />} />
              <Route path="/jobs/:id/edit" element={<JobFormPage />} />
              <Route path="/products" element={<ProductsPage />} />
              <Route path="/products/:id" element={<ProductDetailPage />} />
              <Route path="/printers" element={<PrintersPage />} />
              <Route path="/printers/new" element={<PrinterFormPage />} />
              <Route path="/printers/:id" element={<PrinterDetailPage />} />
              <Route path="/printers/:id/edit" element={<PrinterFormPage />} />
              <Route path="/inventory" element={<InventoryPage />} />
              <Route path="/sales" element={<SalesPage />} />
              <Route path="/sales/new" element={<SaleFormPage />} />
              <Route path="/sales/channels" element={<SalesChannelsPage />} />
              <Route path="/sales/:id" element={<SaleDetailPage />} />
              <Route path="/materials" element={<MaterialsPage />} />
              <Route path="/rates" element={<RatesPage />} />
              <Route path="/customers" element={<CustomersPage />} />
              <Route path="/calculator" element={<CalculatorPage />} />

              {/* Reports section with sub-navigation */}
              <Route path="/reports" element={<ReportsLayout />}>
                <Route index element={<Navigate to="/reports/inventory" replace />} />
                <Route path="inventory" element={<InventoryReportPage />} />
                <Route path="sales" element={<SalesReportPage />} />
                <Route path="pl" element={<PLReportPage />} />
              </Route>

              {/* Admin section with sidebar */}
              <Route path="/admin" element={<AdminLayout />}>
                <Route index element={<Navigate to="/admin/settings" replace />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="users" element={<UsersPage />} />
                <Route path="data" element={<DataPage />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
