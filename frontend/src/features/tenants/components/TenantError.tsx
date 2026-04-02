import { AlertTriangle } from 'lucide-react';

interface TenantErrorProps {
  message: string;
}

export function TenantError({ message }: TenantErrorProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="max-w-md rounded-lg bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
          <AlertTriangle className="h-6 w-6 text-red-600" />
        </div>
        <h2 className="mb-2 text-lg font-semibold text-gray-900">Unable to Load</h2>
        <p className="text-sm text-gray-500">{message}</p>
      </div>
    </div>
  );
}
