import React, { createContext, useEffect, useState } from 'react';
import { tenantApi } from '../api/tenant.api';
import type { TenantContext, TenantInfo } from '../types';
import { TenantLoader } from './TenantLoader';
import { TenantError } from './TenantError';
import { normalizeError } from '@/shared/api/errors';

export const TenantCtx = createContext<TenantContext | null>(null);

interface TenantProviderProps {
  children: React.ReactNode;
}

export function TenantProvider({ children }: TenantProviderProps) {
  const [tenant, setTenant] = useState<TenantInfo | null>(null);
  const [isAdminDomain, setIsAdminDomain] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function resolveTenant() {
      try {
        const { data } = await tenantApi.resolve();

        if (cancelled) return;

        if (data.is_admin_domain) {
          setIsAdminDomain(true);
          setTenant(null);
        } else if (data.id && data.slug && data.name) {
          setTenant({
            id: data.id,
            slug: data.slug,
            name: data.name,
            status: data.status || 'active',
            settings_json: data.settings_json || null,
          });
          setIsAdminDomain(false);
        }
      } catch (err) {
        if (cancelled) return;
        const apiErr = normalizeError(err);
        if (apiErr.status === 403) {
          setError('This organization has been suspended. Please contact support.');
        } else if (apiErr.status === 404) {
          setError('Organization not found. Please check the URL.');
        } else {
          setError('Unable to connect to the server. Please try again later.');
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    resolveTenant();

    return () => {
      cancelled = true;
    };
  }, []);

  if (isLoading) {
    return <TenantLoader />;
  }

  if (error) {
    return <TenantError message={error} />;
  }

  return (
    <TenantCtx.Provider value={{ tenant, isAdminDomain, isLoading, error }}>
      {children}
    </TenantCtx.Provider>
  );
}
