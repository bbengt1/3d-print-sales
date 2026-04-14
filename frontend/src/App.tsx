import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import Layout from '@/components/layout/Layout';
import AdminLayout from '@/components/layout/AdminLayout';
import ProtectedRoute from '@/components/auth/ProtectedRoute';

const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const ControlCenterPage = lazy(() => import('@/pages/ControlCenterPage'));
const JobsPage = lazy(() => import('@/pages/JobsPage'));
const JobDetailPage = lazy(() => import('@/pages/JobDetailPage'));
const JobFormPage = lazy(() => import('@/pages/JobFormPage'));
const MaterialsPage = lazy(() => import('@/pages/MaterialsPage'));
const RatesPage = lazy(() => import('@/pages/RatesPage'));
const CustomersPage = lazy(() => import('@/pages/CustomersPage'));
const ProductsPage = lazy(() => import('@/pages/ProductsPage'));
const ProductEditorPage = lazy(() => import('@/pages/ProductEditorPage'));
const ProductDetailPage = lazy(() => import('@/pages/ProductDetailPage'));
const PrintersPage = lazy(() => import('@/pages/PrintersPage'));
const PrinterDetailPage = lazy(() => import('@/pages/PrinterDetailPage'));
const PrinterFormPage = lazy(() => import('@/pages/PrinterFormPage'));
const InventoryPage = lazy(() => import('@/pages/InventoryPage'));
const SalesPage = lazy(() => import('@/pages/SalesPage'));
const SaleDetailPage = lazy(() => import('@/pages/SaleDetailPage'));
const SaleFormPage = lazy(() => import('@/pages/SaleFormPage'));
const SalesChannelsPage = lazy(() => import('@/pages/SalesChannelsPage'));
const POSPage = lazy(() => import('@/pages/POSPage'));
const CalculatorPage = lazy(() => import('@/pages/CalculatorPage'));
const OrdersPage = lazy(() => import('@/pages/OrdersPage'));
const InsightsPage = lazy(() => import('@/pages/InsightsPage'));
const ReportsLayout = lazy(() => import('@/pages/reports/ReportsLayout'));
const InventoryReportPage = lazy(() => import('@/pages/reports/InventoryReportPage'));
const SalesReportPage = lazy(() => import('@/pages/reports/SalesReportPage'));
const PLReportPage = lazy(() => import('@/pages/reports/PLReportPage'));
const LoginPage = lazy(() => import('@/pages/LoginPage'));
const SettingsPage = lazy(() => import('@/pages/admin/SettingsPage'));
const UsersPage = lazy(() => import('@/pages/admin/UsersPage'));
const DataPage = lazy(() => import('@/pages/admin/DataPage'));
const CamerasPage = lazy(() => import('@/pages/admin/CamerasPage'));
const PrinterMonitorPage = lazy(() => import('@/pages/PrinterMonitorPage'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

function RouteFallback() {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto flex max-w-6xl items-center justify-center px-6 py-24">
        <div className="w-full max-w-3xl animate-pulse space-y-4">
          <div className="h-10 w-56 rounded-2xl bg-card" />
          <div className="h-40 rounded-3xl bg-card" />
          <div className="grid gap-4 md:grid-cols-2">
            <div className="h-32 rounded-3xl bg-card" />
            <div className="h-32 rounded-3xl bg-card" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/print-floor/monitor/:id"
                element={
                  <ProtectedRoute>
                    <PrinterMonitorPage />
                  </ProtectedRoute>
                }
              />
              <Route
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route path="/" element={<Navigate to="/control-center" replace />} />
                <Route path="/control-center" element={<ControlCenterPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />

                <Route path="/print-floor" element={<PrintersPage />} />
                <Route path="/print-floor/printers" element={<PrintersPage />} />
                <Route path="/print-floor/printers/new" element={<PrinterFormPage />} />
                <Route path="/print-floor/printers/:id" element={<PrinterDetailPage />} />
                <Route path="/print-floor/printers/:id/edit" element={<PrinterFormPage />} />

                <Route path="/sell" element={<POSPage />} />
                <Route path="/sell/pos" element={<POSPage />} />
                <Route path="/sell/sales" element={<SalesPage />} />
                <Route path="/sell/sales/new" element={<SaleFormPage />} />
                <Route path="/sell/sales/:id" element={<SaleDetailPage />} />
                <Route path="/sell/channels" element={<SalesChannelsPage />} />

                <Route path="/stock" element={<InventoryPage />} />
                <Route path="/stock/inventory" element={<InventoryPage />} />
                <Route path="/stock/materials" element={<MaterialsPage />} />

                <Route path="/product-studio" element={<ProductsPage />} />
                <Route path="/product-studio/products" element={<ProductsPage />} />
                <Route path="/product-studio/products/new" element={<ProductEditorPage />} />
                <Route path="/product-studio/products/:id" element={<ProductDetailPage />} />
                <Route path="/product-studio/products/:id/edit" element={<ProductEditorPage />} />
                <Route path="/product-studio/calculator" element={<CalculatorPage />} />
                <Route path="/product-studio/rates" element={<RatesPage />} />

                <Route path="/orders" element={<OrdersPage />} />
                <Route path="/orders/jobs" element={<JobsPage />} />
                <Route path="/orders/jobs/new" element={<JobFormPage />} />
                <Route path="/orders/jobs/:id" element={<JobDetailPage />} />
                <Route path="/orders/jobs/:id/edit" element={<JobFormPage />} />
                <Route path="/orders/customers" element={<CustomersPage />} />

                <Route path="/insights" element={<InsightsPage />} />
                <Route path="/insights/reports" element={<Navigate to="/reports/inventory" replace />} />

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
                <Route path="/pos" element={<POSPage />} />
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
                  <Route path="cameras" element={<CamerasPage />} />
                  <Route path="data" element={<DataPage />} />
                </Route>
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
        <Toaster richColors position="top-right" />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
