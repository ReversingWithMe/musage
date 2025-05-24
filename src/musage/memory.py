import sys
import os
import resource
import threading
import subprocess
import atexit
import psutil
from datetime import datetime

from typing import List, Optional

# Global variables for tracking peak memory usage
peak_memory_info = {
    'curr_total_gb': 0,
    'curr_total_mb': 0,
    'curr_timestamp': None,
    'curr_breakdown': None,
    'peak_total_gb': 0,
    'peak_total_mb': 0,
    'peak_timestamp': None,
    'peak_breakdown': None,
    'monitoring_active': False,
    'base_swap': 0
}

def register_mempoll():
    memory_poll()

    # Register the atexit callback
    atexit.register(report_peak_memory)

def get_all_descendants():
    """Get all descendant processes (children, grandchildren, etc.) recursively."""
    try:
        current_process = psutil.Process()
        # recursive=True gets all descendants, not just direct children
        descendants = current_process.children(recursive=True)
        return descendants
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []

def memory_poll() -> None:
    is_linux = sys.platform.startswith('linux')
    is_macos = sys.platform == 'darwin'

    # Start appropriate memory monitoring thread (silent mode)
    stop_monitor = threading.Event()
    if is_linux:
        monitor_thread = threading.Thread(target=memory_monitor_linux, args=(stop_monitor,))
    elif is_macos:
        monitor_thread = threading.Thread(target=memory_monitor_macos, args=(stop_monitor,))
    else:
        monitor_thread = threading.Thread(target=memory_monitor_generic, args=(stop_monitor,))

    monitor_thread.daemon = True
    monitor_thread.start()

def report_peak_memory(epoch: Optional[str] = None) -> None:
    """
    atexit callback function that reports the highest memory usage observed.
    """
    if epoch:
        print("\n" + "=" * 80)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] MEMORY TEST SUMMARY")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {epoch}")
        print("=" * 80)

    if peak_memory_info['peak_total_gb'] > 0:
        print(f"Peak Memory Usage: {peak_memory_info['peak_total_gb']:.2f}GB ({peak_memory_info['peak_total_mb']:.0f}MB)")
        print(f"Peak Observed At: {peak_memory_info['peak_timestamp']}")

        if peak_memory_info['peak_breakdown']:
            breakdown = peak_memory_info['peak_breakdown']
            print(f"Peak Breakdown:")
            print(f"  └─ Parent Process: {breakdown['parent']['memory_mb']:.0f}MB")
            print(f"  └─ Total Children: {breakdown['total_children_memory_mb']:.0f}MB")

            if breakdown['children']:
                print(f"  └─ Individual Children:")
                for child in breakdown['children']:
                    print(f"     └─ Child {child['id']} (PID {child['pid']}): "
                          f"{child['memory_gb']:.2f}GB ({child['memory_mb']:.0f}MB)")

        print("=" * 80)
    else:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] No memory usage data collected")



def read_proc_meminfo(pid):
    """
    Read memory information from /proc/PID/status for a specific process (Linux).
    Returns memory usage in KB.
    """
    try:
        with open(f'/proc/{pid}/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    # Extract memory in KB
                    mem_kb = int(line.split()[1])
                    return mem_kb
    except (FileNotFoundError, PermissionError, ValueError):
        return 0
    return 0

def get_process_memory_macos(pid):
    """
    Get memory usage for a specific process on macOS using ps command.
    Returns memory usage in KB.
    """
    try:
        # Use ps command to get RSS (Resident Set Size) in KB
        result = subprocess.run(
            ['ps', '-o', 'rss=', '-p', str(pid)],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # ps returns RSS in KB on macOS
            mem_kb = int(result.stdout.strip())
            return mem_kb
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError):
        pass
    return 0

def get_memory_usage_linux(process_list):
    """
    Linux-specific memory usage tracking using /proc filesystem.
    Returns detailed memory information for parent and all child processes.
    """
    parent_pid = os.getpid()
    parent_mem_kb = read_proc_meminfo(parent_pid)

    children_info = []
    total_children_mem_kb = 0

    for process in process_list:
        if process.is_alive():
            child_pid = process.pid
            child_mem_kb = read_proc_meminfo(child_pid)
            total_children_mem_kb += child_mem_kb
            children_info.append({
                'id': process.name.split('-')[1] if '-' in process.name else 'unknown',
                'pid': child_pid,
                'memory_kb': child_mem_kb,
                'memory_mb': child_mem_kb / 1024,
                'memory_gb': child_mem_kb / (1024 * 1024)
            })

    total_mem_kb = parent_mem_kb + total_children_mem_kb

    return {
        'parent': {
            'pid': parent_pid,
            'memory_kb': parent_mem_kb,
            'memory_mb': parent_mem_kb / 1024,
            'memory_gb': parent_mem_kb / (1024 * 1024)
        },
        'children': children_info,
        'total_children_memory_kb': total_children_mem_kb,
        'total_children_memory_mb': total_children_mem_kb / 1024,
        'total_children_memory_gb': total_children_mem_kb / (1024 * 1024),
        'total_memory_kb': total_mem_kb,
        'total_memory_mb': total_mem_kb / 1024,
        'total_memory_gb': total_mem_kb / (1024 * 1024)
    }

def get_memory_usage_macos():
    """
    macOS-specific memory usage tracking using ps command.
    Returns detailed memory information for parent and all child processes.
    """
    process_list = get_all_descendants()

    parent_pid = os.getpid()
    parent_mem_kb = get_process_memory_macos(parent_pid)

    children_info = []
    total_children_mem_kb = 0

    for process in process_list:
        if process.is_running():
            child_pid = process.pid
            child_mem_kb = get_process_memory_macos(child_pid)
            total_children_mem_kb += child_mem_kb
            children_info.append({
                'id': process.name().split('-')[1] if '-' in process.name() else 'unknown',
                'pid': child_pid,
                'memory_kb': child_mem_kb,
                'memory_mb': child_mem_kb / 1024,
                'memory_gb': child_mem_kb / (1024 * 1024)
            })

    total_mem_kb = parent_mem_kb + total_children_mem_kb

    return {
        'parent': {
            'pid': parent_pid,
            'memory_kb': parent_mem_kb,
            'memory_mb': parent_mem_kb / 1024,
            'memory_gb': parent_mem_kb / (1024 * 1024)
        },
        'children': children_info,
        'total_children_memory_kb': total_children_mem_kb,
        'total_children_memory_mb': total_children_mem_kb / 1024,
        'total_children_memory_gb': total_children_mem_kb / (1024 * 1024),
        'total_memory_kb': total_mem_kb,
        'total_memory_mb': total_mem_kb / 1024,
        'total_memory_gb': total_mem_kb / (1024 * 1024)
    }

def get_memory_usage_generic():
    """
    Generic memory usage using resource module (fallback for non-Linux/macOS systems).
    """
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        children_usage = resource.getrusage(resource.RUSAGE_CHILDREN)

        if sys.platform == 'darwin':  # macOS
            self_memory_mb = usage.ru_maxrss / (1024 * 1024)
            children_memory_mb = children_usage.ru_maxrss / (1024 * 1024)
        else:  # Linux and others
            self_memory_mb = usage.ru_maxrss / 1024
            children_memory_mb = children_usage.ru_maxrss / 1024

        total_memory_mb = self_memory_mb + children_memory_mb
        return total_memory_mb, self_memory_mb, children_memory_mb

    except Exception as e:
        return 0, 0, 0

def memory_monitor_linux(stop_event, process_list):
    """
    Linux-specific memory monitoring using /proc filesystem.
    Silently tracks peak memory usage every 5 seconds.
    """
    global peak_memory_info
    peak_memory_info['monitoring_active'] = True

    while not stop_event.is_set():
        mem_info = get_memory_usage_linux(process_list)

        # Update peak memory if current usage is higher
        if mem_info['total_memory_gb'] > peak_memory_info['peak_total_gb']:
            peak_memory_info['peak_total_gb'] = mem_info['total_memory_gb']
            peak_memory_info['peak_total_mb'] = mem_info['total_memory_mb']
            peak_memory_info['peak_timestamp'] = datetime.now().strftime('%H:%M:%S')
            peak_memory_info['peak_breakdown'] = mem_info.copy()
        peak_memory_info['curr_total_gb'] = mem_info['total_memory_gb']
        peak_memory_info['curr_total_mb'] = mem_info['total_memory_mb']
        peak_memory_info['curr_timestamp'] = datetime.now().strftime('%H:%M:%S')
        peak_memory_info['curr_breakdown'] = mem_info.copy()

        # Wait 5 seconds or until stop event is set
        stop_event.wait(1)

def memory_monitor_macos(stop_event):
    """
    macOS-specific memory monitoring using ps command.
    Silently tracks peak memory usage every 5 seconds.
    """
    global peak_memory_info
    peak_memory_info['monitoring_active'] = True

    while not stop_event.is_set():
        mem_info = get_memory_usage_macos()

        # Update peak memory if current usage is higher
        if mem_info['total_memory_gb'] > peak_memory_info['peak_total_gb']:
            peak_memory_info['peak_total_gb'] = mem_info['total_memory_gb']
            peak_memory_info['peak_total_mb'] = mem_info['total_memory_mb']
            peak_memory_info['peak_timestamp'] = datetime.now().strftime('%H:%M:%S')
            peak_memory_info['peak_breakdown'] = mem_info.copy()
        peak_memory_info['curr_total_gb'] = mem_info['total_memory_gb']
        peak_memory_info['curr_total_mb'] = mem_info['total_memory_mb']
        peak_memory_info['curr_timestamp'] = datetime.now().strftime('%H:%M:%S')
        peak_memory_info['curr_breakdown'] = mem_info.copy()

        # Wait 5 seconds or until stop event is set
        stop_event.wait(1)

def memory_monitor_generic(stop_event):
    """
    Generic memory monitoring (fallback for non-Linux/macOS systems).
    Silently tracks peak memory usage every 5 seconds.
    """
    global peak_memory_info
    peak_memory_info['monitoring_active'] = True

    while not stop_event.is_set():
        total_mb, self_mb, children_mb = get_memory_usage_generic()
        total_gb = total_mb / 1024

        # Update peak memory if current usage is higher
        if total_gb > peak_memory_info['peak_total_gb']:
            peak_memory_info['peak_total_gb'] = total_gb
            peak_memory_info['peak_total_mb'] = total_mb
            peak_memory_info['peak_timestamp'] = datetime.now().strftime('%H:%M:%S')
            peak_memory_info['peak_breakdown'] = {
                'parent': {'memory_mb': self_mb},
                'total_children_memory_mb': children_mb,
                'children': []  # Generic monitoring doesn't track individual children
            }
        peak_memory_info['curr_total_gb'] = total_gb
        peak_memory_info['curr_total_mb'] = total_mb
        peak_memory_info['curr_timestamp'] = datetime.now().strftime('%H:%M:%S')
        peak_memory_info['curr_breakdown'] = {
            'parent': {'memory_mb': self_mb},
            'total_children_memory_mb': children_mb,
            'children': []  # Generic monitoring doesn't track individual children
        }

        # Wait 5 seconds or until stop event is set
        stop_event.wait(1)
