import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import { projectsApi } from '../api/projects.api';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';
import { ClientSelector } from '@/features/clients/components/ClientSelector';

const schema = z.object({
  project_name: z.string().min(1, 'Project name is required'),
  country: z.string().min(1, 'Country is required'),
  city: z.string().min(1, 'City is required'),
  due_date: z.string().min(1, 'Due date is required'),
});

type FormData = z.infer<typeof schema>;

export function CreateProjectPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [countries, setCountries] = useState<string[]>([]);
  const [submitError, setSubmitError] = useState('');

  // Client selection state
  const [clientId, setClientId] = useState<string | null>(searchParams.get('clientId'));
  const [clientError, setClientError] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { country: 'KSA' },
  });

  useEffect(() => {
    projectsApi.getCountries().then(({ data }) => setCountries(data)).catch(() => {});
  }, []);

  const onSubmit = async (formData: FormData) => {
    if (!clientId) {
      setClientError('Please select a client');
      return;
    }
    setClientError('');
    setSubmitError('');
    try {
      const { data } = await projectsApi.create({
        ...formData,
        client_id: clientId,
      });
      navigate(`/projects/${data.id}`);
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/projects')}
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100"
        >
          <ArrowLeft className="h-4 w-4 text-gray-500" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">New Project</h1>
          <p className="text-sm text-gray-500">Fill in the project details below</p>
        </div>
      </div>

      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <Input
            label="Project Name"
            placeholder="e.g. Office Tower Phase 1"
            error={errors.project_name?.message}
            {...register('project_name')}
          />

          <div className="relative">
            <ClientSelector
              value={clientId}
              onChange={(id) => {
                setClientId(id);
                setClientError('');
              }}
              error={clientError}
            />
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Country</label>
              <select
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                {...register('country')}
              >
                {countries.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              {errors.country && (
                <p className="mt-1 text-sm text-red-600">{errors.country.message}</p>
              )}
            </div>

            <Input
              label="City"
              placeholder="e.g. Riyadh"
              error={errors.city?.message}
              {...register('city')}
            />
          </div>

          <div>
            <Input
              label="Due Date"
              type="date"
              error={errors.due_date?.message}
              {...register('due_date')}
            />
          </div>

          {submitError && <p className="text-sm text-red-600">{submitError}</p>}

          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => navigate('/projects')}>
              Cancel
            </Button>
            <Button type="submit" isLoading={isSubmitting}>
              Create Project
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
