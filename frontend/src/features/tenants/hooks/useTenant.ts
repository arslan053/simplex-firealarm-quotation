import { useContext } from 'react';
import { TenantCtx } from '../components/TenantProvider';

export function useTenant() {
  const ctx = useContext(TenantCtx);
  if (!ctx) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return ctx;
}
