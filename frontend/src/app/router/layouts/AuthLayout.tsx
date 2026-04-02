import { Outlet } from 'react-router-dom';
import { useTenant } from '@/features/tenants/hooks/useTenant';

export function AuthLayout() {
  const { tenant, isAdminDomain } = useTenant();
  const displayName = isAdminDomain ? 'Admin Portal' : tenant?.name || 'Quotation Platform';

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600">
            <span className="text-xl font-bold text-white">Q</span>
          </div>
          <p className="text-sm text-gray-500">{displayName}</p>
        </div>
        <div className="rounded-lg bg-white p-8 shadow-sm">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
