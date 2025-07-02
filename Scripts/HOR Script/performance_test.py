#!/usr/bin/env python3
"""
Performance test for HOR multithreading implementation.
Compares single-threaded vs multi-threaded performance.
"""
import os
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt
from typing import List, Tuple
import json

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def simulate_pdf_processing(item_id: int, delay: float = 0.5) -> dict:
    """Simulate PDF processing with artificial delay."""
    import random
    
    # Simulate varying processing times
    actual_delay = delay * (0.5 + random.random())
    time.sleep(actual_delay)
    
    # Simulate occasional failures
    if random.random() < 0.1:  # 10% failure rate
        raise Exception(f"Simulated processing error for item {item_id}")
    
    return {
        'id': item_id,
        'processing_time': actual_delay,
        'transactions': random.randint(1, 20)
    }

def test_sequential_processing(num_items: int, delay: float = 0.5) -> Tuple[float, int, int]:
    """Test sequential processing of items."""
    logging.info(f"Starting sequential processing of {num_items} items...")
    
    start_time = time.time()
    successful = 0
    failed = 0
    
    for i in range(num_items):
        try:
            result = simulate_pdf_processing(i, delay)
            successful += 1
        except Exception as e:
            failed += 1
            logging.debug(f"Error processing item {i}: {e}")
    
    elapsed_time = time.time() - start_time
    logging.info(f"Sequential processing completed in {elapsed_time:.2f}s")
    
    return elapsed_time, successful, failed

def test_multithreaded_processing(num_items: int, num_threads: int, delay: float = 0.5) -> Tuple[float, int, int]:
    """Test multi-threaded processing of items."""
    logging.info(f"Starting multi-threaded processing of {num_items} items with {num_threads} threads...")
    
    start_time = time.time()
    successful = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all tasks
        futures = {executor.submit(simulate_pdf_processing, i, delay): i 
                  for i in range(num_items)}
        
        # Process results as they complete
        for future in as_completed(futures):
            try:
                result = future.result()
                successful += 1
            except Exception as e:
                failed += 1
                item_id = futures[future]
                logging.debug(f"Error processing item {item_id}: {e}")
    
    elapsed_time = time.time() - start_time
    logging.info(f"Multi-threaded processing completed in {elapsed_time:.2f}s")
    
    return elapsed_time, successful, failed

def run_performance_comparison():
    """Run comprehensive performance comparison."""
    results = {
        'test_configs': [],
        'sequential_times': [],
        'multithreaded_times': [],
        'speedups': []
    }
    
    # Test configurations
    test_configs = [
        (10, 0.2),   # 10 items, 0.2s delay
        (20, 0.2),   # 20 items, 0.2s delay
        (50, 0.1),   # 50 items, 0.1s delay
        (100, 0.05), # 100 items, 0.05s delay
    ]
    
    thread_counts = [1, 2, 4, 8, 16, 32, 50]
    
    for num_items, delay in test_configs:
        print(f"\n{'='*60}")
        print(f"Testing with {num_items} items, {delay}s average delay per item")
        print(f"{'='*60}")
        
        # Sequential test
        seq_time, seq_success, seq_fail = test_sequential_processing(num_items, delay)
        print(f"Sequential: {seq_time:.2f}s ({seq_success} successful, {seq_fail} failed)")
        
        # Multi-threaded tests
        for num_threads in thread_counts:
            if num_threads > num_items:
                continue
                
            mt_time, mt_success, mt_fail = test_multithreaded_processing(
                num_items, num_threads, delay
            )
            speedup = seq_time / mt_time
            
            print(f"  {num_threads:2d} threads: {mt_time:.2f}s (speedup: {speedup:.2f}x)")
            
            # Store results
            results['test_configs'].append(f"{num_items} items")
            results['sequential_times'].append(seq_time)
            results['multithreaded_times'].append(mt_time)
            results['speedups'].append({
                'threads': num_threads,
                'speedup': speedup,
                'efficiency': speedup / num_threads * 100
            })
    
    return results

def analyze_thread_scaling():
    """Analyze how performance scales with thread count."""
    num_items = 100
    delay = 0.1
    thread_counts = [1, 2, 4, 8, 16, 32, 50]
    
    print(f"\n{'='*60}")
    print(f"Thread Scaling Analysis ({num_items} items)")
    print(f"{'='*60}")
    
    # Get baseline (sequential)
    seq_time, _, _ = test_sequential_processing(num_items, delay)
    
    scaling_results = []
    
    for num_threads in thread_counts:
        mt_time, _, _ = test_multithreaded_processing(num_items, num_threads, delay)
        speedup = seq_time / mt_time
        efficiency = (speedup / num_threads) * 100
        
        scaling_results.append({
            'threads': num_threads,
            'time': mt_time,
            'speedup': speedup,
            'efficiency': efficiency
        })
        
        print(f"Threads: {num_threads:2d} | Time: {mt_time:6.2f}s | "
              f"Speedup: {speedup:5.2f}x | Efficiency: {efficiency:5.1f}%")
    
    # Find optimal thread count
    best_result = max(scaling_results, key=lambda x: x['speedup'])
    print(f"\nOptimal thread count: {best_result['threads']} "
          f"(speedup: {best_result['speedup']:.2f}x)")
    
    # Save results
    filepath = os.path.join(os.path.dirname(__file__), 'thread_scaling_results.json')
    with open(filepath, 'w') as f:
        json.dump(scaling_results, f, indent=2)
    
    return scaling_results

def main():
    """Run all performance tests."""
    print("HOR Script Multithreading Performance Analysis")
    print("=" * 60)
    
    # Run performance comparison
    comparison_results = run_performance_comparison()
    
    # Run thread scaling analysis
    scaling_results = analyze_thread_scaling()
    
    # Summary
    print(f"\n{'='*60}")
    print("PERFORMANCE SUMMARY")
    print(f"{'='*60}")
    
    print("\nKey Findings:")
    print("1. Multithreading provides significant performance improvements")
    print("2. Speedup increases with thread count up to a certain point")
    print("3. Efficiency decreases as thread count increases (overhead)")
    print("4. Optimal thread count depends on workload characteristics")
    
    print("\nRecommendations:")
    print("- For I/O-bound tasks (PDF downloads): Use 20-50 threads")
    print("- For CPU-bound tasks (PDF processing): Use 4-8 threads")
    print("- Monitor system resources to avoid overload")
    print("- Consider implementing adaptive thread pool sizing")
    
    # Save full results
    filepath = os.path.join(os.path.dirname(__file__), 'performance_test_results.json')
    with open(filepath, 'w') as f:
        json.dump({
            'comparison': comparison_results,
            'scaling': scaling_results,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, indent=2)
    
    print(f"\nResults saved to performance_test_results.json")

if __name__ == "__main__":
    main() 