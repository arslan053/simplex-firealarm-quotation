# Frontend Module Prompt Template

Use this template when adding new feature modules to the frontend.

## Where New Feature Modules Go

All features live under `src/features/<feature-name>/` with this structure:

```
src/features/<feature-name>/
├── api/                  # API call functions (use shared axios client)
│   └── <feature>.api.ts
├── components/           # Feature-specific components
│   └── ...
├── hooks/                # Feature-specific hooks (data fetching, logic)
│   └── ...
├── pages/                # Page-level components (rendered by router)
│   └── ...
├── types/                # TypeScript types/interfaces for this feature
│   └── index.ts
├── store/                # (ONLY if needed) Redux slice for cross-feature state
│   └── ...
└── utils/                # Feature-specific utility functions
    └── ...
```

## How to Add Routes

1. Open `src/app/router/index.tsx`
2. Import your page components
3. Add routes inside the appropriate layout:
   - Public pages → inside `AuthLayout`
   - Protected pages → inside `AppLayout` (wrapped by `ProtectedRoute`)

```tsx
// Example: adding a BoQ module
import { BoqListPage } from '@/features/boq/pages/BoqListPage';
import { BoqDetailPage } from '@/features/boq/pages/BoqDetailPage';

// Inside the router definition, under AppLayout:
{ path: 'boq', element: <BoqListPage /> },
{ path: 'boq/:id', element: <BoqDetailPage /> },
```

4. Add navigation links in `src/app/router/layouts/AppLayout.tsx`

## How to Add API Calls + Query Hooks

### 1. Define the API function

```tsx
// src/features/boq/api/boq.api.ts
import { apiClient } from '@/shared/api/client';
import type { BoqItem, CreateBoqPayload } from '../types';

export const boqApi = {
  list: (projectId: string) =>
    apiClient.get<BoqItem[]>(`/tenant/projects/${projectId}/boq`),

  create: (projectId: string, data: CreateBoqPayload) =>
    apiClient.post<BoqItem>(`/tenant/projects/${projectId}/boq`, data),
};
```

### 2. Create query hooks

```tsx
// src/features/boq/hooks/useBoqItems.ts
import { useQuery } from '@tanstack/react-query';
import { boqApi } from '../api/boq.api';

export function useBoqItems(projectId: string) {
  return useQuery({
    queryKey: ['boq', projectId],
    queryFn: () => boqApi.list(projectId).then(r => r.data),
    enabled: !!projectId,
  });
}
```

### 3. Create mutation hooks

```tsx
// src/features/boq/hooks/useCreateBoq.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { boqApi } from '../api/boq.api';

export function useCreateBoq(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateBoqPayload) => boqApi.create(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['boq', projectId] });
    },
  });
}
```

## Where to Put UI Components

- **Feature-specific components** → `src/features/<feature>/components/`
- **Shared/reusable primitives** (Button, Input, Modal) → `src/shared/ui/`
- **Shared composed components** (DataTable, FileUploader) → `src/shared/components/`

Rule: If a component is used by 2+ features, move it to `shared/`.

## Where Redux Is Allowed

Redux is **rarely needed**. Default to:
- `useState`/`useReducer` for component-local state
- React Query for server state
- React Context for cross-cutting concerns (auth, tenant)

Only use Redux (in `src/features/<feature>/store/`) when you have:
- Complex client-side state shared across multiple features
- State that doesn't come from the server

Example: a complex multi-step form wizard with cross-feature interactions.

## Conventions

- All API calls go through `src/shared/api/client.ts` (the configured axios instance)
- Types matching backend schemas go in `src/features/<feature>/types/`
- Use `zod` schemas for form validation in pages
- Use `react-hook-form` for all forms
- Use `sonner` toast for user feedback
- Use `lucide-react` for icons
- Use `cn()` from `src/shared/utils/cn.ts` for conditional Tailwind classes
