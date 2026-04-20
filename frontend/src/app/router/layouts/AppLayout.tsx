import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Building2, ContactRound, CreditCard, FolderOpen, LayoutDashboard, LogOut, Settings, User, Users, Menu, X } from 'lucide-react';
import { useState } from 'react';

import { useAuth } from '@/features/auth/hooks/useAuth';
import { useTenant } from '@/features/tenants/hooks/useTenant';
import { cn } from '@/shared/utils/cn';
import { Badge } from '@/shared/ui/Badge';
import { BillingAlert } from '@/features/billing/components/BillingAlert';

interface NavItem {
  to: string;
  label: string;
  icon: React.ElementType;
}

function getNavItems(role: string, isAdminDomain: boolean): NavItem[] {
  const items: NavItem[] = [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  ];

  if (isAdminDomain && role === 'super_admin') {
    items.push({ to: '/companies', label: 'Companies', icon: Building2 });
  }

  if (!isAdminDomain && (role === 'admin' || role === 'employee')) {
    items.push({ to: '/clients', label: 'Clients', icon: ContactRound });
    items.push({ to: '/projects', label: 'Projects', icon: FolderOpen });
  }

  if (!isAdminDomain && role === 'admin') {
    items.push({ to: '/users', label: 'Team Members', icon: Users });
  }

  if (!isAdminDomain) {
    items.push({ to: '/settings', label: 'Settings', icon: Settings });
  }

  if (!isAdminDomain && role === 'admin') {
    items.push({ to: '/billing', label: 'Billing', icon: CreditCard });
  }

  return items;
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const { tenant, isAdminDomain } = useTenant();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const orgName = isAdminDomain ? 'Admin Portal' : tenant?.name || 'Quotation';
  const navItems = getNavItems(user?.role || 'employee', isAdminDomain);

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 w-64 transform bg-white shadow-sm transition-transform duration-200 lg:relative lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex h-16 items-center gap-3 border-b px-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
              <span className="text-sm font-bold text-white">Q</span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-gray-900">{orgName}</p>
            </div>
            <button
              className="lg:hidden"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="h-5 w-5 text-gray-400" />
            </button>
          </div>

          {/* Nav */}
          <nav className="flex-1 space-y-1 px-3 py-4">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
                  )
                }
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* User section */}
          <div className="border-t p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100">
                <User className="h-4 w-4 text-gray-500" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-gray-900">{user?.email}</p>
                <Badge>{user?.role.replace('_', ' ')}</Badge>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <div className="flex flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-16 items-center justify-between border-b bg-white px-4 lg:px-6">
          <button
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5 text-gray-500" />
          </button>

          <div className="flex-1" />

          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700"
          >
            <LogOut className="h-4 w-4" />
            <span className="hidden sm:inline">Sign Out</span>
          </button>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 lg:p-6">
          <BillingAlert />
          <Outlet />
        </main>
      </div>
    </div>
  );
}
