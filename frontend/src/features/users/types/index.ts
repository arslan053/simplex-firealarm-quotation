export interface TenantUser {
  id: string;
  email: string;
  name: string | null;
  role: 'admin' | 'employee';
  is_active: boolean;
  must_change_password: boolean;
  created_at: string | null;
}

export interface UserListResponse {
  items: TenantUser[];
  total: number;
}

export interface InviteUserRequest {
  email: string;
  role: 'admin' | 'employee';
  first_name: string;
  last_name: string;
}

export interface UpdateRoleRequest {
  role: 'admin' | 'employee';
}
