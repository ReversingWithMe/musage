#!/usr/bin/env python3
"""
Memory Test Script: Spawns 5 child processes, each allocating 1GB of RAM.
Children spawn 15 seconds apart, hold memory for 5 minutes, then exit.
Total memory usage: ~5GB for 5 minutes.
Silent monitoring with peak memory reporting at exit via atexit.
"""

import multiprocessing
import time
import sys
import os
from datetime import datetime
from musage import register_mempoll

def allocate_memory_child(child_id, gb_size=1):
    """
    Child process function that allocates specified GB of memory.

    Args:
        child_id (int): Identifier for the child process
        gb_size (int): Amount of memory to allocate in GB
    """
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {child_id} (PID: {os.getpid()}) starting memory allocation...")

        # Allocate memory: Create a list of 1MB chunks to reach target size
        # Using 1MB chunks (1024*1024 bytes) for better memory management
        chunk_size = 1024 * 1024  # 1 MB
        chunks_needed = gb_size * 1024  # Number of 1MB chunks for target GB

        memory_pool = []
        for i in range(chunks_needed):
            # Allocate 1MB of data (filled with zeros)
            chunk = bytearray(chunk_size)
            memory_pool.append(chunk)

            # Progress indicator every 100MB
            if (i + 1) % 100 == 0:
                allocated_mb = (i + 1)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {child_id}: {allocated_mb}MB allocated")

        allocated_gb = len(memory_pool) * chunk_size / (1024**3)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {child_id}: Successfully allocated {allocated_gb:.2f}GB")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {child_id}: Holding memory for 5 minutes...")

        # Hold the memory for 5 minutes (300 seconds)
        time.sleep(300)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {child_id}: Releasing memory and exiting")

    except MemoryError:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {child_id}: Failed to allocate memory - MemoryError")
        sys.exit(1)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {child_id}: Error - {e}")
        sys.exit(1)

def main():
    """
    Main function that spawns 5 child processes with 15-second intervals.
    Uses platform-specific memory monitoring (Linux /proc, macOS ps, or generic fallback).
    Memory monitoring runs silently and reports peak usage at exit.
    """

    register_mempoll()

    is_linux = sys.platform.startswith('linux')
    is_macos = sys.platform == 'darwin'

    # Determine monitoring method
    if is_linux:
        monitor_method = "Linux /proc filesystem"
    elif is_macos:
        monitor_method = "macOS ps command"
    else:
        monitor_method = "Generic resource module"

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Memory Test Script Starting")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Platform: {sys.platform}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Memory monitoring: {monitor_method} (silent mode)")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Parent PID: {os.getpid()}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Will spawn 5 children, each allocating 1GB RAM")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 15-second delay between spawns")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Peak memory usage will be reported at exit")
    print("=" * 80)

    try:
        # Spawn 5 child processes with 15-second delays
        for i in range(5):
            child_id = i + 1

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Spawning child {child_id}...")

            # Create and start child process
            process = multiprocessing.Process(
                target=allocate_memory_child,
                args=(child_id,),
                name=f"MemoryChild-{child_id}"
            )
            process.start()

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {child_id} spawned (PID: {process.pid})")

            # Wait 15 seconds before spawning next child (except for the last one)
            if i < 4:  # Don't wait after the last child
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting 15 seconds before next spawn...")
                time.sleep(15)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] All 5 children spawned successfully")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Target memory usage: ~5GB")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Memory will be held for 5 minutes per child")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring memory usage silently...")
        print("=" * 80)

        # Wait for all child processes to complete
        for i, process in enumerate(processes, 1):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for child {i} to complete...")
            process.join()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Child {i} completed with exit code: {process.exitcode}")

        print("=" * 80)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] All child processes completed")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Memory test script finished")

    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Interrupted by user (Ctrl+C)")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Terminating child processes...")

        # Terminate all child processes
        for i, process in enumerate(processes, 1):
            if process.is_alive():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Terminating child {i}...")
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Force killing child {i}...")
                    process.kill()

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cleanup completed")

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error in main process: {e}")

if __name__ == "__main__":
    # Use 'fork' on Unix systems (Linux, macOS) for better performance
    # Use 'spawn' on Windows
    if sys.platform != 'win32':
        try:
            multiprocessing.set_start_method('fork', force=True)
            print(f"Using 'fork' method for multiprocessing")
        except RuntimeError:
            multiprocessing.set_start_method('spawn', force=True)
            print(f"Using 'spawn' method for multiprocessing")
    else:
        multiprocessing.set_start_method('spawn', force=True)
        print(f"Using 'spawn' method for multiprocessing")

    main()
