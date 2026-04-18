import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import {
  LogOut,
  User as UserIcon,
  Shield,
  Building,
  KeyRound,
  Pencil,
} from 'lucide-react';

import { useAuth } from '@/features/auth/hooks/useAuth';
import { useTenant } from '@/features/tenants/hooks/useTenant';
import { authApi } from '@/features/auth/api/auth.api';
import { Card } from '@/shared/ui/Card';
import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

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

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Current password is required'),
    new_password: z.string().min(8, 'New password must be at least 8 characters'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type ChangePasswordFormData = z.infer<typeof changePasswordSchema>;

const profileSchema = z.object({
  first_name: z.string().min(1, 'First name is required').regex(/^\S+$/, 'First name must be a single word'),
  last_name: z.string().min(1, 'Last name is required'),
});

type ProfileFormData = z.infer<typeof profileSchema>;

function parseName(name: string | null): { first_name: string; last_name: string } {
  if (!name) return { first_name: '', last_name: '' };
  const spaceIdx = name.indexOf(' ');
  if (spaceIdx === -1) return { first_name: name, last_name: '' };
  return { first_name: name.slice(0, spaceIdx), last_name: name.slice(spaceIdx + 1) };
}

export function AccountSettingsPage() {
  const { user, logout, refreshUser } = useAuth();
  const { tenant, isAdminDomain } = useTenant();
  const navigate = useNavigate();
  const [editingName, setEditingName] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
  });

  const {
    register: registerProfile,
    handleSubmit: handleProfileSubmit,
    formState: { errors: profileErrors, isSubmitting: profileSubmitting },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: parseName(user?.name ?? null),
  });

  if (!user) return null;

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  const onSubmit = async (data: ChangePasswordFormData) => {
    try {
      await authApi.changePassword({
        current_password: data.current_password,
        new_password: data.new_password,
      });
      toast.success('Password changed successfully');
      reset();
      await refreshUser();
    } catch (err) {
      const apiErr = normalizeError(err);
      toast.error(apiErr.message);
    }
  };

  const onProfileSubmit = async (data: ProfileFormData) => {
    try {
      await authApi.updateProfile({
        first_name: data.first_name,
        last_name: data.last_name,
      });
      toast.success('Name updated successfully');
      setEditingName(false);
      await refreshUser();
    } catch (err) {
      const apiErr = normalizeError(err);
      toast.error(apiErr.message);
    }
  };

  return (
    <div className="space-y-6">
      {/* Profile Card */}
      <Card>
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-indigo-100">
              <UserIcon className="h-7 w-7 text-indigo-600" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-gray-900">
                  {user.name || user.email}
                </h2>
                {!editingName && (
                  <button
                    onClick={() => setEditingName(true)}
                    className="text-gray-400 hover:text-gray-600"
                    title="Edit name"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                )}
              </div>
              {user.name && (
                <p className="text-sm text-gray-500">{user.email}</p>
              )}
              <Badge variant={roleBadgeVariant[user.role]}>
                {roleLabel[user.role]}
              </Badge>
            </div>
          </div>

          {editingName && (
            <form onSubmit={handleProfileSubmit(onProfileSubmit)} className="border-t pt-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="First Name"
                  placeholder="John"
                  error={profileErrors.first_name?.message}
                  {...registerProfile('first_name')}
                />
                <Input
                  label="Last Name"
                  placeholder="Doe"
                  error={profileErrors.last_name?.message}
                  {...registerProfile('last_name')}
                />
              </div>
              <div className="mt-3 flex gap-2">
                <Button type="submit" isLoading={profileSubmitting}>
                  Save Name
                </Button>
                <Button type="button" variant="outline" onClick={() => setEditingName(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          )}

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

      {/* Change Password Card */}
      <Card>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100">
              <KeyRound className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Change Password</h3>
              <p className="text-sm text-gray-500">Update your account password</p>
            </div>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" autoComplete="off">
            <Input
              label="Current Password"
              type="password"
              placeholder="Your current password"
              autoComplete="new-password"
              error={errors.current_password?.message}
              {...register('current_password')}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="New Password"
                type="password"
                placeholder="At least 8 characters"
                autoComplete="new-password"
                error={errors.new_password?.message}
                {...register('new_password')}
              />
              <Input
                label="Confirm New Password"
                type="password"
                placeholder="Confirm new password"
                autoComplete="new-password"
                error={errors.confirm_password?.message}
                {...register('confirm_password')}
              />
            </div>
            <div>
              <Button type="submit" isLoading={isSubmitting}>
                Update Password
              </Button>
            </div>
          </form>
        </div>
      </Card>

      {/* Sign Out */}
      <div className="flex justify-end">
        <Button variant="danger" onClick={handleLogout}>
          <LogOut className="mr-2 h-4 w-4" />
          Sign Out
        </Button>
      </div>
    </div>
  );
}
