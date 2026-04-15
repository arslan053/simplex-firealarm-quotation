import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';

import { AuthLayout } from './layouts/AuthLayout';
import { AppLayout } from './layouts/AppLayout';
import { ProtectedRoute } from './ProtectedRoute';

import { LoginPage } from '@/features/auth/pages/LoginPage';
import { ForgotPasswordPage } from '@/features/auth/pages/ForgotPasswordPage';
import { ResetPasswordPage } from '@/features/auth/pages/ResetPasswordPage';
import { ChangePasswordPage } from '@/features/auth/pages/ChangePasswordPage';
import { ProfilePage } from '@/features/auth/pages/ProfilePage';
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage';
import { CompaniesPage } from '@/features/admin/pages/CompaniesPage';
import { UsersPage } from '@/features/users/pages/UsersPage';
import { ProjectListPage } from '@/features/projects/pages/ProjectListPage';
import { CreateProjectPage } from '@/features/projects/pages/CreateProjectPage';
import { ProjectDetailPage } from '@/features/projects/pages/ProjectDetailPage';
import { DeviceSelectionPage } from '@/features/projects/pages/DeviceSelectionPage';
import { ProjectResultsPage } from '@/features/projects/pages/ProjectResultsPage';
import { PricingPage } from '@/features/projects/pages/PricingPage';
import { ClientListPage } from '@/features/clients/pages/ClientListPage';
import { ClientDetailPage } from '@/features/clients/pages/ClientDetailPage';
import { PriceListPage } from '@/features/tenant-pricing/pages/PriceListPage';
import { SettingsPage } from '@/features/settings/pages/SettingsPage';

const router = createBrowserRouter([
  {
    path: '/auth',
    element: <AuthLayout />,
    children: [
      { path: 'login', element: <LoginPage /> },
      { path: 'forgot-password', element: <ForgotPasswordPage /> },
      { path: 'reset-password', element: <ResetPasswordPage /> },
      {
        path: 'change-password',
        element: (
          <ProtectedRoute>
            <ChangePasswordPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'companies', element: <CompaniesPage /> },
{ path: 'users', element: <UsersPage /> },
      { path: 'clients', element: <ClientListPage /> },
      { path: 'clients/:clientId', element: <ClientDetailPage /> },
      { path: 'projects', element: <ProjectListPage /> },
      { path: 'projects/new', element: <CreateProjectPage /> },
      { path: 'projects/:projectId', element: <ProjectDetailPage /> },
      { path: 'projects/:projectId/results', element: <ProjectResultsPage /> },
      { path: 'projects/:projectId/device-selection', element: <DeviceSelectionPage /> },
      { path: 'projects/:projectId/pricing', element: <PricingPage /> },
      { path: 'price-list', element: <PriceListPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'profile', element: <ProfilePage /> },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
