import { AxiosError } from 'axios';

export interface ApiError {
  message: string;
  status: number;
}

const STATUS_MESSAGES: Record<number, string> = {
  400: 'Invalid request. Please check your input and try again.',
  401: 'Your session has expired. Please log in again.',
  403: 'You do not have permission to perform this action.',
  404: 'The requested resource was not found.',
  409: 'This conflicts with existing data. Please review and try again.',
  413: 'The file is too large. Please reduce its size and try again.',
  422: 'The submitted data is invalid. Please check your input.',
  429: 'Too many requests. Please wait a moment and try again.',
  500: 'Something went wrong on our end. Please try again later.',
  502: 'The server is temporarily unavailable. Please try again later.',
  503: 'The service is currently unavailable. Please try again later.',
};

export function normalizeError(error: unknown): ApiError {
  if (error instanceof AxiosError) {
    const status = error.response?.status ?? 500;
    const detail = error.response?.data?.detail;

    let message: string;
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail) && detail.length > 0) {
      // FastAPI validation errors: [{loc: [...], msg: "...", type: "..."}]
      message = detail.map((e) => e.msg || String(e)).join('. ');
    } else {
      message = STATUS_MESSAGES[status] || 'An unexpected error occurred. Please try again.';
    }

    return { message, status };
  }
  if (error instanceof Error) {
    return { message: error.message, status: 500 };
  }
  return { message: 'An unexpected error occurred. Please try again.', status: 500 };
}
