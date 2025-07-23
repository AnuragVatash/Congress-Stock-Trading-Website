"use client";

import { useEffect } from 'react';

// Simple performance debugging utilities
export function DebugPerformance() {
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Monitor long-running JavaScript tasks
    const observer = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      entries.forEach((entry) => {
        if (entry.duration > 50) { // Log tasks longer than 50ms
          console.warn(`🐌 Long Task: ${entry.name} took ${entry.duration.toFixed(2)}ms`);
        }
      });
    });

    observer.observe({ entryTypes: ['measure', 'navigation'] });

    // Monitor input event handlers
    const originalAddEventListener = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function(this: EventTarget, type: string, listener: EventListenerOrEventListenerObject | null, options?: boolean | AddEventListenerOptions) {
      if (type === 'input' || type === 'change') {
        const wrappedListener = function(this: EventTarget, event: Event) {
          const start = performance.now();
          
          // Call original listener
          if (typeof listener === 'function') {
            listener.call(this, event);
          } else if (listener && typeof listener.handleEvent === 'function') {
            listener.handleEvent(event);
          }
          
          const end = performance.now();
          const duration = end - start;
          
          if (duration > 5) { // Log input handlers longer than 5ms
            const target = event.target as HTMLElement;
            const targetInfo = target.tagName + (target.id ? `#${target.id}` : '') + (target.className ? `.${target.className.split(' ')[0]}` : '');
            console.warn(`⚡ Slow Input Handler: ${targetInfo} took ${duration.toFixed(2)}ms`);
          }
        };
        
        return originalAddEventListener.call(this, type, wrappedListener, options);
      }
      
      return originalAddEventListener.call(this, type, listener, options);
    };

    return () => {
      observer.disconnect();
      EventTarget.prototype.addEventListener = originalAddEventListener;
    };
  }, []);

  return null;
}

// Add this to measure specific operations
export function measureSync<T>(operationName: string, fn: () => T): T {
  const start = performance.now();
  const result = fn();
  const end = performance.now();
  const duration = end - start;

  if (duration > 1) {
    console.log(`📊 ${operationName}: ${duration.toFixed(2)}ms`);
  }

  return result;
}

// Add this to measure async operations
export async function measureAsync<T>(operationName: string, fn: () => Promise<T>): Promise<T> {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();
  const duration = end - start;

  if (duration > 10) {
    console.log(`📊 ${operationName} (async): ${duration.toFixed(2)}ms`);
  }

  return result;
}

// Hook to detect excessive re-renders
export function useRenderCount(componentName: string) {
  const renderCount = ++useRenderCount.counts[componentName] || (useRenderCount.counts[componentName] = 1);
  
  if (renderCount > 10) {
    console.warn(`🔄 ${componentName} has re-rendered ${renderCount} times - possible performance issue`);
  }
  
  return renderCount;
}

useRenderCount.counts = {} as Record<string, number>; 