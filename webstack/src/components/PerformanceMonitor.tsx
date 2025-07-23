"use client";

import { useEffect, useRef } from 'react';

type PerformanceMonitorProps = {
  componentName: string;
  enabled?: boolean;
};

export default function PerformanceMonitor({ componentName, enabled = false }: PerformanceMonitorProps) {
  const startTimeRef = useRef<number>(0);
  const renderCountRef = useRef<number>(0);

  useEffect(() => {
    if (!enabled) return;

    const startTime = performance.now();
    startTimeRef.current = startTime;
    renderCountRef.current++;

    return () => {
      const endTime = performance.now();
      const duration = endTime - startTimeRef.current;
      
      if (duration > 10) { // Only log if operation takes more than 10ms
        console.warn(`🚀 Performance: ${componentName} render #${renderCountRef.current} took ${duration.toFixed(2)}ms`);
      }
    };
  });

  return null; // This is a utility component, renders nothing
}

// Hook for monitoring specific operations
export function usePerformanceMonitor(componentName: string, enabled: boolean = false) {
  const measureOperation = (operationName: string, fn: () => unknown) => {
    if (!enabled) return fn();

    const start = performance.now();
    const result = fn();
    const end = performance.now();
    const duration = end - start;

    if (duration > 1) { // Log operations that take more than 1ms
      console.log(`📊 ${componentName}.${operationName}: ${duration.toFixed(2)}ms`);
    }

    return result;
  };

  const measureAsyncOperation = async (operationName: string, fn: () => Promise<unknown>) => {
    if (!enabled) return await fn();

    const start = performance.now();
    const result = await fn();
    const end = performance.now();
    const duration = end - start;

    if (duration > 10) { // Log async operations that take more than 10ms
      console.log(`📊 ${componentName}.${operationName} (async): ${duration.toFixed(2)}ms`);
    }

    return result;
  };

  return { measureOperation, measureAsyncOperation };
} 