import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { CheckCircle } from 'lucide-react';

import { authApi } from '../api/auth.api';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

const forgotSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email'),
});

type ForgotFormData = z.infer<typeof forgotSchema>;

export function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotFormData>({
    resolver: zodResolver(forgotSchema),
  });

  const onSubmit = async (data: ForgotFormData) => {
    try {
      await authApi.forgotPassword({ email: data.email });
      setSubmitted(true);
    } catch (err) {
      const apiErr = normalizeError(err);
      toast.error(apiErr.message);
    }
  };

  if (submitted) {
    return (
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
          <CheckCircle className="h-6 w-6 text-green-600" />
        </div>
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Check your email</h2>
        <p className="mb-4 text-sm text-gray-500">
          If an account exists with that email, you'll receive a password reset link.
        </p>
        <Link to="/auth/login" className="text-sm text-indigo-600 hover:text-indigo-500">
          Back to Sign In
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold text-gray-900">Forgot Password</h1>
        <p className="mt-1 text-sm text-gray-500">
          Enter your email and we'll send you a reset link
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Input
          label="Email"
          type="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register('email')}
        />

        <Button type="submit" className="w-full" isLoading={isSubmitting}>
          Send Reset Link
        </Button>
      </form>

      <div className="mt-4 text-center">
        <Link to="/auth/login" className="text-sm text-indigo-600 hover:text-indigo-500">
          Back to Sign In
        </Link>
      </div>
    </div>
  );
}
