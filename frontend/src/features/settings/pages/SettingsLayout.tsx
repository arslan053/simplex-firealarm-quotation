import { Navigate, NavLink, Outlet, useLocation } from 'react-router-dom';
import { Building, DollarSign, User } from 'lucide-react';

import { useAuth } from '@/features/auth/hooks/useAuth';
import { cn } from '@/shared/utils/cn';

interface SectionCard {
  to: string;
  label: string;
  description: string;
  icon: React.ElementType;
  adminOnly: boolean;
}

const sections: SectionCard[] = [
  {
    to: '/settings/general',
    label: 'Company Profile',
    description: 'Letterhead, signature & branding',
    icon: Building,
    adminOnly: true,
  },
  {
    to: '/settings/pricing',
    label: 'Pricing',
    description: 'Product prices & templates',
    icon: DollarSign,
    adminOnly: true,
  },
  {
    to: '/settings/account',
    label: 'Account',
    description: 'Profile & preferences',
    icon: User,
    adminOnly: false,
  },
];

export function SettingsLayout() {
  const { user } = useAuth();
  const location = useLocation();
  const isAdmin = user?.role === 'admin';

  // Non-admin: block admin-only routes, redirect to account
  if (!isAdmin) {
    const path = location.pathname;
    if (path === '/settings' || path === '/settings/general' || path === '/settings/pricing') {
      return <Navigate to="/settings/account" replace />;
    }

    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-sm text-gray-500">Manage your account</p>
        </div>
        <Outlet />
      </div>
    );
  }

  // Admin: default to general
  if (location.pathname === '/settings') {
    return <Navigate to="/settings/general" replace />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500">Manage your company configuration and account</p>
      </div>

      {/* Section cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        {sections.map((section) => (
          <NavLink
            key={section.to}
            to={section.to}
            className={({ isActive }) =>
              cn(
                'flex items-start gap-3 rounded-lg border-2 bg-white p-4 shadow-sm transition-all hover:shadow-md',
                isActive
                  ? 'border-indigo-600 ring-1 ring-indigo-600'
                  : 'border-gray-200 hover:border-gray-300',
              )
            }
          >
            <div
              className={cn(
                'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                section.to === '/settings/general' && 'bg-indigo-100',
                section.to === '/settings/pricing' && 'bg-amber-100',
                section.to === '/settings/account' && 'bg-sky-100',
              )}
            >
              <section.icon
                className={cn(
                  'h-5 w-5',
                  section.to === '/settings/general' && 'text-indigo-600',
                  section.to === '/settings/pricing' && 'text-amber-600',
                  section.to === '/settings/account' && 'text-sky-600',
                )}
              />
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-gray-900">{section.label}</p>
              <p className="text-sm text-gray-500">{section.description}</p>
            </div>
          </NavLink>
        ))}
      </div>

      {/* Selected section content */}
      <Outlet />
    </div>
  );
}
