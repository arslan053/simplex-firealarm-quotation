import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { authApi } from '../api/auth.api';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

const resetSchema = z
  .object({
    new_password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type ResetFormData = z.infer<typeof resetSchema>;

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetFormData>({
    resolver: zodResolver(resetSchema),
  });

  if (!token) {
    return (
      <div className="text-center">
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Invalid Reset Link</h2>
        <p className="text-sm text-gray-500">
          This reset link is invalid or has expired. Please request a new one.
        </p>
      </div>
    );
  }

  const onSubmit = async (data: ResetFormData) => {
    try {
      await authApi.resetPassword({ token, new_password: data.new_password });
      toast.success('Password has been reset successfully');
      navigate('/auth/login');
    } catch (err) {
      const apiErr = normalizeError(err);
      toast.error(apiErr.message);
    }
  };

  return (
    <div>
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-gray-900">Reset Password</h1>
        <p className="mt-1 text-sm text-gray-500">Enter your new password</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="New Password"
          type="password"
          placeholder="At least 8 characters"
          error={errors.new_password?.message}
          {...register('new_password')}
        />

        <Input
          label="Confirm Password"
          type="password"
          placeholder="Confirm your password"
          error={errors.confirm_password?.message}
          {...register('confirm_password')}
        />

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          Reset Password
        </Button>
      </form>
    </div>
  );
}
