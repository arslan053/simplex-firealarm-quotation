import React from 'react';
import { Toaster } from 'sonner';
import { QueryProvider } from './QueryProvider';
import { ErrorBoundary } from '@/shared/components/ErrorBoundary';
import { AuthProvider } from '@/features/auth/components/AuthProvider';

interface AppProvidersProps {
  children: React.ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryProvider>
      <Toaster position="top-right" richColors />
      <ErrorBoundary>
        <AuthProvider>{children}</AuthProvider>
      </ErrorBoundary>
    </QueryProvider>
  );
}
