import { AxiosError } from 'axios';

export interface ApiError {
  message: string;
  status: number;
}

export function normalizeError(error: unknown): ApiError {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    const message = typeof detail === 'string' ? detail : error.message;
    return {
      message,
      status: error.response?.status ?? 500,
    };
  }
  if (error instanceof Error) {
    return { message: error.message, status: 500 };
  }
  return { message: 'An unexpected error occurred', status: 500 };
}
