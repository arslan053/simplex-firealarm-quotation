export interface ProductDetail {
  code: string;
  price_sar: number;
}

export interface PricingItem {
  id: string;
  section: 'device' | 'panel';
  row_number: number;
  description: string | null;
  quantity: number;
  unit_cost_sar: number;
  total_sar: number;
  product_details: ProductDetail[];
}

export interface PricingResponse {
  project_id: string;
  project_name: string;
  calculated_at: string;
  usd_to_sar_rate: number;
  items: PricingItem[];
  device_subtotal: number;
  panel_subtotal: number;
  subtotal: number;
}
