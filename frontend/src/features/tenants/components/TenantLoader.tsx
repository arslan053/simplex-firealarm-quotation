import { LoadingSpinner } from '@/shared/components/LoadingSpinner';

export function TenantLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <LoadingSpinner size="lg" label="Loading..." />
    </div>
  );
}
