import { useEffect, useState } from 'react';
import { Building2, FolderOpen, LayoutDashboard, Users, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '@/features/auth/hooks/useAuth';
import { useTenant } from '@/features/tenants/hooks/useTenant';
import { Card } from '@/shared/ui/Card';
import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';
import { adminApi } from '@/features/admin/api/admin.api';
import { usersApi } from '@/features/users/api/users.api';
import { projectsApi } from '@/features/projects/api/projects.api';

const roleLabel = {
  super_admin: 'Super Admin',
  admin: 'Admin',
  employee: 'Employee',
};

export function DashboardPage() {
  const { user } = useAuth();
  const { tenant, isAdminDomain } = useTenant();
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    companies: 0,
    totalUsers: 0,
    teamMembers: 0,
    projects: 0,
  });

  useEffect(() => {
    if (!user) return;

    if (user.role === 'super_admin' && isAdminDomain) {
      adminApi.listTenants().then(({ data }) => {
        const totalUsers = data.items.reduce((s, t) => s + t.user_count, 0);
        setStats((prev) => ({ ...prev, companies: data.total, totalUsers }));
      }).catch(() => {});
    } else if (user.role === 'admin' && !isAdminDomain) {
      Promise.all([
        usersApi.list(),
        projectsApi.list({ page: 1, limit: 1 }),
      ]).then(([usersRes, projectsRes]) => {
        setStats((prev) => ({
          ...prev,
          teamMembers: usersRes.data.total,
          projects: projectsRes.data.pagination.total,
        }));
      }).catch(() => {});
    } else if (user.role === 'employee' && !isAdminDomain) {
      projectsApi.list({ page: 1, limit: 1 }).then(({ data }) => {
        setStats((prev) => ({ ...prev, projects: data.pagination.total }));
      }).catch(() => {});
    }
  }, [user, isAdminDomain]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500">Welcome back, {user.name || user.email}</p>
      </div>

      {/* Role & Org info */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100">
              <LayoutDashboard className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Role</p>
              <p className="font-medium text-gray-900">{roleLabel[user.role]}</p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
              <Building2 className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Organization</p>
              <p className="font-medium text-gray-900">
                {isAdminDomain ? 'Platform Admin' : tenant?.name || 'N/A'}
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100">
              <LayoutDashboard className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Status</p>
              <Badge variant="success">Active</Badge>
            </div>
          </div>
        </Card>
      </div>

      {/* Super Admin: quick stats + action */}
      {user.role === 'super_admin' && isAdminDomain && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
                  <Building2 className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">Companies</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.companies}</p>
                </div>
              </div>
            </Card>
            <Card>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-100">
                  <Users className="h-5 w-5 text-teal-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">Total Users (all companies)</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.totalUsers}</p>
                </div>
              </div>
            </Card>
          </div>
          <Button variant="outline" onClick={() => navigate('/companies')}>
            Manage Companies
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Admin / Employee on tenant domain: project + team stats */}
      {!isAdminDomain && (user.role === 'admin' || user.role === 'employee') && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100">
                  <FolderOpen className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-gray-500">
                    {user.role === 'admin' ? 'All Projects' : 'My Projects'}
                  </p>
                  <p className="text-2xl font-bold text-gray-900">{stats.projects}</p>
                </div>
              </div>
            </Card>
            {user.role === 'admin' && (
              <Card>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-100">
                    <Users className="h-5 w-5 text-teal-600" />
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Team Members</p>
                    <p className="text-2xl font-bold text-gray-900">{stats.teamMembers}</p>
                  </div>
                </div>
              </Card>
            )}
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => navigate('/projects')}>
              View Projects
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            {user.role === 'admin' && (
              <Button variant="outline" onClick={() => navigate('/users')}>
                Manage Team
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
