import { useNavigate } from 'react-router-dom';
import { LogOut, User as UserIcon, Shield, Building } from 'lucide-react';

import { useAuth } from '../hooks/useAuth';
import { useTenant } from '@/features/tenants/hooks/useTenant';
import { Card } from '@/shared/ui/Card';
import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';

const roleBadgeVariant = {
  super_admin: 'danger' as const,
  admin: 'warning' as const,
  employee: 'default' as const,
};

const roleLabel = {
  super_admin: 'Super Admin',
  admin: 'Admin',
  employee: 'Employee',
};

export function ProfilePage() {
  const { user, logout } = useAuth();
  const { tenant, isAdminDomain } = useTenant();
  const navigate = useNavigate();

  if (!user) return null;

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Profile</h1>

      <Card>
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-indigo-100">
              <UserIcon className="h-8 w-8 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{user.email}</h2>
              <Badge variant={roleBadgeVariant[user.role]}>
                {roleLabel[user.role]}
              </Badge>
            </div>
          </div>

          <div className="border-t pt-4">
            <dl className="space-y-3">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-gray-400" />
                <dt className="text-sm font-medium text-gray-500">Role</dt>
                <dd className="text-sm text-gray-900">{roleLabel[user.role]}</dd>
              </div>

              {(tenant || user.tenant) && (
                <div className="flex items-center gap-2">
                  <Building className="h-4 w-4 text-gray-400" />
                  <dt className="text-sm font-medium text-gray-500">Organization</dt>
                  <dd className="text-sm text-gray-900">
                    {tenant?.name || user.tenant?.name}
                  </dd>
                </div>
              )}

              {isAdminDomain && (
                <div className="flex items-center gap-2">
                  <Building className="h-4 w-4 text-gray-400" />
                  <dt className="text-sm font-medium text-gray-500">Context</dt>
                  <dd className="text-sm text-gray-900">Platform Administration</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-gray-900">Password</h3>
            <p className="text-sm text-gray-500">Change your account password</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => navigate('/auth/change-password')}>
            Change Password
          </Button>
        </div>
      </Card>

      <div className="flex justify-end">
        <Button variant="danger" onClick={handleLogout}>
          <LogOut className="mr-2 h-4 w-4" />
          Sign Out
        </Button>
      </div>
    </div>
  );
}
