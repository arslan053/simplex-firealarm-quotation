import { TenantProvider } from '@/features/tenants/components/TenantProvider';
import { AppProviders } from './providers/AppProviders';
import { AppRouter } from './router';

export default function App() {
  return (
    <TenantProvider>
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </TenantProvider>
  );
}
