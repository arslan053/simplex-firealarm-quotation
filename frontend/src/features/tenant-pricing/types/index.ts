export interface TenantProductPrice {
  product_id: string;
  code: string;
  description: string;
  category: string;
  price: number;
  currency: string;
}

export interface PriceListResponse {
  items: TenantProductPrice[];
  total: number;
  prices_set: number;
}

export interface PriceUpdateItem {
  product_id: string;
  price: number;
}

export interface TemplateValidationError {
  row: number;
  expected_code: string;
  got_code: string;
  message: string;
}

export interface UploadResponse {
  updated: number;
  errors: TemplateValidationError[];
}
