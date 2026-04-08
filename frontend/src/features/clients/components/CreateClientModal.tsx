import { useState } from 'react';
import { X, UserPlus } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import { clientsApi } from '../api/clients.api';
import type { Client } from '../types';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

const schema = z.object({
  name: z.string().min(1, 'Contact name is required'),
  company_name: z.string().min(1, 'Company name is required'),
  email: z.string().email('Invalid email').or(z.literal('')).optional(),
  phone: z.string().optional(),
  address: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

interface CreateClientModalProps {
  onClose: () => void;
  onCreated: (client: Client) => void;
}

export function CreateClientModal({ onClose, onCreated }: CreateClientModalProps) {
  const [submitError, setSubmitError] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', company_name: '', email: '', phone: '', address: '' },
  });

  const onSubmit = async (formData: FormData) => {
    setSubmitError('');
    try {
      const { data } = await clientsApi.create({
        name: formData.name,
        company_name: formData.company_name,
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        address: formData.address || undefined,
      });
      onCreated(data);
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      <div className="relative z-10 mx-4 w-full max-w-lg rounded-xl bg-white shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <UserPlus className="h-5 w-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-gray-900">New Client</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 hover:bg-gray-100 transition-colors"
          >
            <X className="h-5 w-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit(onSubmit)} className="px-6 py-5 space-y-4">
          <Input
            label="Contact Name"
            placeholder="e.g. Ahmed Hassan"
            error={errors.name?.message}
            {...register('name')}
          />
          <Input
            label="Company Name"
            placeholder="e.g. Al Rajhi Corp"
            error={errors.company_name?.message}
            {...register('company_name')}
          />
          <Input
            label="Email"
            type="email"
            placeholder="e.g. contact@company.com"
            error={errors.email?.message}
            {...register('email')}
          />
          <Input
            label="Phone"
            placeholder="e.g. +966 50 123 4567"
            error={errors.phone?.message}
            {...register('phone')}
          />
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Address</label>
            <textarea
              rows={2}
              placeholder="e.g. Riyadh, Saudi Arabia"
              className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              {...register('address')}
            />
          </div>

          {submitError && <p className="text-sm text-red-600">{submitError}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSubmitting}>
              Create Client
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
