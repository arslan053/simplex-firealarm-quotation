import React from 'react';
import { cn } from '@/shared/utils/cn';

interface CardProps {
  className?: string;
  children: React.ReactNode;
}

export function Card({ className, children }: CardProps) {
  return (
    <div className={cn('rounded-lg bg-white p-6 shadow-sm', className)}>
      {children}
    </div>
  );
}
