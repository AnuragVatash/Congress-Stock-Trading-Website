"""
Observability utilities for congressional trading document processing.
Provides metrics collection, performance tracking, and system monitoring.
"""
import time
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
from functools import wraps
import threading

class MetricsCollector:
    """
    Collects and tracks various metrics for the document processing system.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.counters = defaultdict(int)
        self.histograms = defaultdict(list)
        self.gauges = defaultdict(float)
        self.timers = {}
        self.events = deque(maxlen=1000)  # Keep last 1000 events
        self.lock = threading.Lock()
        
        # Performance tracking
        self.processing_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.success_counts = defaultdict(int)
        
        # Rate tracking (per minute)
        self.rate_windows = defaultdict(lambda: deque(maxlen=60))
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        with self.lock:
            key = self._make_key(name, tags)
            self.counters[key] += value
            self._record_event('counter', name, value, tags)
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a value in a histogram."""
        with self.lock:
            key = self._make_key(name, tags)
            self.histograms[key].append(value)
            # Keep only last 1000 values
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
            self._record_event('histogram', name, value, tags)
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric."""
        with self.lock:
            key = self._make_key(name, tags)
            self.gauges[key] = value
            self._record_event('gauge', name, value, tags)
    
    def start_timer(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Start a timer and return a timer ID."""
        timer_id = f"{name}_{int(time.time() * 1000000)}"
        with self.lock:
            self.timers[timer_id] = {
                'name': name,
                'start_time': time.time(),
                'tags': tags or {}
            }
        return timer_id
    
    def stop_timer(self, timer_id: str):
        """Stop a timer and record the duration."""
        with self.lock:
            if timer_id in self.timers:
                timer_info = self.timers.pop(timer_id)
                duration = time.time() - timer_info['start_time']
                self.record_histogram(f"{timer_info['name']}_duration", duration, timer_info['tags'])
                return duration
        return None
    
    def record_processing_time(self, operation: str, duration: float, success: bool = True):
        """Record processing time for an operation."""
        with self.lock:
            self.processing_times[operation].append(duration)
            if success:
                self.success_counts[operation] += 1
            else:
                self.error_counts[operation] += 1
            
            # Update rate tracking
            now = time.time()
            self.rate_windows[operation].append(now)
    
    def get_rate(self, operation: str, window_seconds: int = 60) -> float:
        """Get the rate of operations per second over a time window."""
        with self.lock:
            now = time.time()
            cutoff = now - window_seconds
            
            # Count operations in the window
            count = sum(1 for timestamp in self.rate_windows[operation] if timestamp >= cutoff)
            return count / window_seconds
    
    def get_average_duration(self, operation: str, window_size: int = 100) -> Optional[float]:
        """Get average duration for an operation over recent samples."""
        with self.lock:
            times = self.processing_times[operation]
            if not times:
                return None
            
            recent_times = times[-window_size:] if len(times) > window_size else times
            return sum(recent_times) / len(recent_times)
    
    def get_error_rate(self, operation: str) -> float:
        """Get error rate for an operation."""
        with self.lock:
            total = self.success_counts[operation] + self.error_counts[operation]
            if total == 0:
                return 0.0
            return self.error_counts[operation] / total
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        with self.lock:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'histogram_stats': {},
                'performance': {}
            }
            
            # Calculate histogram statistics
            for key, values in self.histograms.items():
                if values:
                    summary['histogram_stats'][key] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'avg': sum(values) / len(values),
                        'p50': self._percentile(values, 50),
                        'p95': self._percentile(values, 95),
                        'p99': self._percentile(values, 99)
                    }
            
            # Add performance metrics
            for operation in self.processing_times:
                summary['performance'][operation] = {
                    'avg_duration': self.get_average_duration(operation),
                    'error_rate': self.get_error_rate(operation),
                    'rate_per_sec': self.get_rate(operation),
                    'total_successes': self.success_counts[operation],
                    'total_errors': self.error_counts[operation]
                }
            
            return summary
    
    def _make_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """Create a key from name and tags."""
        if not tags:
            return name
        tag_str = ','.join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def _record_event(self, event_type: str, name: str, value: Any, tags: Optional[Dict[str, str]]):
        """Record an event for debugging/auditing."""
        event = {
            'timestamp': time.time(),
            'type': event_type,
            'name': name,
            'value': value,
            'tags': tags or {}
        }
        self.events.append(event)
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

# Global metrics collector
_metrics = MetricsCollector()

def get_metrics() -> MetricsCollector:
    """Get global metrics collector."""
    return _metrics

def timer(operation_name: str, tags: Optional[Dict[str, str]] = None):
    """Decorator to time function execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            metrics = get_metrics()
            timer_id = metrics.start_timer(operation_name, tags)
            try:
                result = func(*args, **kwargs)
                duration = metrics.stop_timer(timer_id)
                metrics.record_processing_time(operation_name, duration, success=True)
                return result
            except Exception as e:
                duration = metrics.stop_timer(timer_id)
                if duration:
                    metrics.record_processing_time(operation_name, duration, success=False)
                raise
        return wrapper
    return decorator

def track_operation(operation_name: str, tags: Optional[Dict[str, str]] = None):
    """Context manager to track operation metrics."""
    class OperationTracker:
        def __init__(self, op_name: str, op_tags: Optional[Dict[str, str]]):
            self.operation_name = op_name
            self.tags = op_tags or {}
            self.start_time = None
            self.metrics = get_metrics()
        
        def __enter__(self):
            self.start_time = time.time()
            self.metrics.increment_counter(f"{self.operation_name}_started", tags=self.tags)
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - self.start_time
            success = exc_type is None
            
            self.metrics.record_processing_time(self.operation_name, duration, success)
            
            if success:
                self.metrics.increment_counter(f"{self.operation_name}_completed", tags=self.tags)
            else:
                self.metrics.increment_counter(f"{self.operation_name}_failed", tags=self.tags)
    
    return OperationTracker(operation_name, tags)

def log_metrics_summary(logger: Optional[logging.Logger] = None):
    """Log a summary of current metrics."""
    if logger is None:
        logger = logging.getLogger(__name__)
    
    metrics = get_metrics()
    summary = metrics.get_metrics_summary()
    
    logger.info("=== METRICS SUMMARY ===")
    logger.info(f"Timestamp: {summary['timestamp']}")
    
    # Log performance metrics
    if summary['performance']:
        logger.info("Performance Metrics:")
        for operation, stats in summary['performance'].items():
            logger.info(f"  {operation}:")
            logger.info(f"    Avg Duration: {stats['avg_duration']:.3f}s" if stats['avg_duration'] else "    Avg Duration: N/A")
            logger.info(f"    Error Rate: {stats['error_rate']:.1%}")
            logger.info(f"    Rate: {stats['rate_per_sec']:.2f}/sec")
            logger.info(f"    Success/Error: {stats['total_successes']}/{stats['total_errors']}")
    
    # Log top counters
    if summary['counters']:
        logger.info("Top Counters:")
        top_counters = sorted(summary['counters'].items(), key=lambda x: x[1], reverse=True)[:10]
        for name, value in top_counters:
            logger.info(f"  {name}: {value}")

def save_metrics_to_file(filepath: str):
    """Save current metrics to a JSON file."""
    metrics = get_metrics()
    summary = metrics.get_metrics_summary()
    
    try:
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        logging.info(f"Metrics saved to {filepath}")
    except Exception as e:
        logging.error(f"Failed to save metrics to {filepath}: {e}")

# Predefined metrics for common operations
def track_document_processing(doc_id: str, doc_type: str = "unknown"):
    """Track document processing metrics."""
    return track_operation("document_processing", {"doc_type": doc_type, "doc_id": doc_id})

def track_llm_request(model: str = "unknown"):
    """Track LLM request metrics."""
    return track_operation("llm_request", {"model": model})

def track_database_operation(operation: str):
    """Track database operation metrics."""
    return track_operation("database_operation", {"operation": operation})

def track_ocr_processing(engine: str = "unknown"):
    """Track OCR processing metrics."""
    return track_operation("ocr_processing", {"engine": engine}) 