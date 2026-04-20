import { useEffect, useRef, useState } from 'react';

import { config } from '@/app/config/env';

declare global {
  interface Window {
    Moyasar?: {
      init: (options: Record<string, unknown>) => void;
    };
  }
}

interface Props {
  amount: number;
  currency: string;
  description: string;
  metadata: Record<string, string>;
  callbackUrl: string;
  onCompleted?: (payment: unknown) => void;
  onFailure?: (error: unknown) => void;
}

const MOYASAR_JS = 'https://cdn.moyasar.com/mpf/1.14.0/moyasar.js';
const MOYASAR_CSS = 'https://cdn.moyasar.com/mpf/1.14.0/moyasar.css';

function ensureMoyasarLoaded(): Promise<void> {
  return new Promise((resolve, reject) => {
    // Already available
    if (window.Moyasar) {
      resolve();
      return;
    }

    // Load CSS if not already present
    if (!document.querySelector(`link[href="${MOYASAR_CSS}"]`)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = MOYASAR_CSS;
      document.head.appendChild(link);
    }

    // Load JS if not already present
    let script = document.querySelector(`script[src="${MOYASAR_JS}"]`) as HTMLScriptElement | null;
    if (!script) {
      script = document.createElement('script');
      script.src = MOYASAR_JS;
      document.head.appendChild(script);
    }

    // Poll for window.Moyasar (script may take a moment to execute)
    let attempts = 0;
    const interval = setInterval(() => {
      attempts++;
      if (window.Moyasar) {
        clearInterval(interval);
        resolve();
      } else if (attempts > 50) {
        clearInterval(interval);
        reject(new Error('Moyasar SDK failed to initialize'));
      }
    }, 100);
  });
}

export function MoyasarPaymentForm({
  amount,
  currency,
  description,
  metadata,
  callbackUrl,
  onCompleted,
  onFailure,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const initializedRef = useRef(false);
  const [sdkReady, setSdkReady] = useState(false);
  const [error, setError] = useState('');

  // Load Moyasar SDK
  useEffect(() => {
    let cancelled = false;
    ensureMoyasarLoaded()
      .then(() => { if (!cancelled) setSdkReady(true); })
      .catch(() => { if (!cancelled) setError('Failed to load payment form. Please refresh the page.'); });
    return () => { cancelled = true; };
  }, []);

  // Init form once SDK is confirmed ready
  useEffect(() => {
    if (!sdkReady || !window.Moyasar || initializedRef.current || !containerRef.current) return;

    initializedRef.current = true;

    window.Moyasar.init({
      element: containerRef.current,
      amount,
      currency,
      description,
      publishable_api_key: config.moyasarPublishableKey,
      callback_url: callbackUrl,
      metadata,
      methods: ['creditcard', 'stcpay'],
      credit_card: {
        save_card: true,
      },
      on_completed: (payment: unknown) => {
        onCompleted?.(payment);
      },
      on_failure: (err: unknown) => {
        onFailure?.(err);
      },
    });

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
      initializedRef.current = false;
    };
  }, [sdkReady, amount, currency, description, metadata, callbackUrl, onCompleted, onFailure]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (!sdkReady) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-gray-500">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-indigo-600" />
        Loading payment form...
      </div>
    );
  }

  return <div ref={containerRef} className="mysr-form" />;
}
