import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { authApi } from '../api/auth.api';
import { useAuth } from '../hooks/useAuth';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

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

export function ChangePasswordPage() {
  const { refreshUser, user } = useAuth();
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
  });

  const onSubmit = async (data: ChangePasswordFormData) => {
    try {
      await authApi.changePassword({
        current_password: data.current_password,
        new_password: data.new_password,
      });
      toast.success('Password changed successfully');
      await refreshUser();
      navigate('/');
    } catch (err) {
      const apiErr = normalizeError(err);
      toast.error(apiErr.message);
    }
  };

  return (
    <div>
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-gray-900">Change Password</h1>
        {user?.must_change_password && (
          <p className="mt-1 text-sm text-amber-600">
            You must change your password before continuing.
          </p>
        )}
        {!user?.must_change_password && (
          <p className="mt-1 text-sm text-gray-500">Update your account password</p>
        )}
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Current Password"
          type="password"
          placeholder="Your current password"
          error={errors.current_password?.message}
          {...register('current_password')}
        />

        <Input
          label="New Password"
          type="password"
          placeholder="At least 8 characters"
          error={errors.new_password?.message}
          {...register('new_password')}
        />

        <Input
          label="Confirm New Password"
          type="password"
          placeholder="Confirm new password"
          error={errors.confirm_password?.message}
          {...register('confirm_password')}
        />

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          Change Password
        </Button>
      </form>
    </div>
  );
}
