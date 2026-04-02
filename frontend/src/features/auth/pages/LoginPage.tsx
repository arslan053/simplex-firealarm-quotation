import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '../hooks/useAuth';
import { useTenant } from '@/features/tenants/hooks/useTenant';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email'),
  password: z.string().min(1, 'Password is required'),
});

type LoginFormData = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { login } = useAuth();
  const { tenant, isAdminDomain } = useTenant();
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    try {
      await login(data.email, data.password);
      toast.success('Logged in successfully');
      navigate('/');
    } catch (err) {
      const apiErr = normalizeError(err);
      toast.error(apiErr.message);
    }
  };

  const title = isAdminDomain ? 'Admin Portal' : tenant?.name || 'Sign In';

  return (
    <div>
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        <p className="mt-1 text-sm text-gray-500">Sign in to your account</p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Email"
          type="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register('email')}
        />

        <Input
          label="Password"
          type="password"
          placeholder="Enter your password"
          error={errors.password?.message}
          {...register('password')}
        />

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          Sign In
        </Button>
      </form>

      <div className="mt-4 text-center">
        <Link to="/auth/forgot-password" className="text-sm text-indigo-600 hover:text-indigo-500">
          Forgot your password?
        </Link>
      </div>
    </div>
  );
}
