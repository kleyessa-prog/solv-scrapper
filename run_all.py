#!/usr/bin/env python3
"""
Run both the patient form monitor and API server simultaneously.

This script starts:
1. The FastAPI server (api.py) to serve patient data
2. The patient form monitor (monitor_patient_form.py) to capture data

Both processes run concurrently and can be stopped with Ctrl+C.
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path
from typing import Optional

# Color codes for terminal output
class Colors:
    API = '\033[94m'      # Blue
    MONITOR = '\033[92m'  # Green
    ERROR = '\033[91m'    # Red
    WARNING = '\033[93m'  # Yellow
    RESET = '\033[0m'     # Reset
    BOLD = '\033[1m'      # Bold


def print_api(message: str):
    """Print message with API prefix."""
    print(f"{Colors.API}[API]{Colors.RESET} {message}")


def print_monitor(message: str):
    """Print message with Monitor prefix."""
    print(f"{Colors.MONITOR}[MONITOR]{Colors.RESET} {message}")


def print_error(message: str):
    """Print error message."""
    print(f"{Colors.ERROR}[ERROR]{Colors.RESET} {message}")


def print_info(message: str):
    """Print info message."""
    print(f"{Colors.BOLD}[INFO]{Colors.RESET} {message}")


def check_requirements():
    """Check if required environment variables and files exist."""
    errors = []
    
    # Check for SOLVHEALTH_QUEUE_URL
    if not os.getenv('SOLVHEALTH_QUEUE_URL'):
        errors.append("SOLVHEALTH_QUEUE_URL environment variable is not set")
    
    # Check if required files exist
    if not Path('api.py').exists():
        errors.append("api.py not found")
    
    if not Path('monitor_patient_form.py').exists():
        errors.append("monitor_patient_form.py not found")
    
    if errors:
        print_error("Missing requirements:")
        for error in errors:
            print_error(f"  - {error}")
        print()
        print_info("Please set SOLVHEALTH_QUEUE_URL, e.g.:")
        print_info("  export SOLVHEALTH_QUEUE_URL='https://manage.solvhealth.com/queue?location_ids=AXjwbE'")
        return False
    
    return True


def wait_for_api(host: str = 'localhost', port: int = 8000, timeout: int = 30):
    """Wait for API server to be ready."""
    import socket
    import time
    
    print_info(f"Waiting for API server to start on {host}:{port}...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print_info("API server is ready!")
                time.sleep(1)  # Give it a moment to fully initialize
                return True
        except Exception:
            pass
        
        time.sleep(0.5)
    
    print_error(f"API server did not start within {timeout} seconds")
    return False


def stream_output(process, prefix_func, process_name):
    """Stream output from a process with prefix."""
    import threading
    
    def stream():
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    prefix_func(line.rstrip())
        except Exception as e:
            print_error(f"Error streaming {process_name} output: {e}")
    
    thread = threading.Thread(target=stream, daemon=True)
    thread.start()
    return thread


def main():
    """Main function to run both processes."""
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Get configuration
    api_host = os.getenv('API_HOST', '0.0.0.0')
    api_port = int(os.getenv('API_PORT', '8000'))
    wait_for_api_ready = os.getenv('WAIT_FOR_API', 'true').lower() == 'true'
    
    # Process management
    api_process = None
    monitor_process = None
    
    def signal_handler(sig, frame):
        """Handle Ctrl+C gracefully."""
        print()
        print_info("Shutting down...")
        
        if monitor_process:
            print_monitor("Stopping monitor...")
            monitor_process.terminate()
            try:
                monitor_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                monitor_process.kill()
        
        if api_process:
            print_api("Stopping API server...")
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()
        
        print_info("Shutdown complete. Goodbye!")
        sys.exit(0)
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Print header
    print()
    print("=" * 70)
    print(f"{Colors.BOLD}🏥 Patient Form Monitor + API Server{Colors.RESET}")
    print("=" * 70)
    print()
    
    # Start API server
    print_info("Starting services...")
    print()
    
    # Start API server as subprocess
    print_api(f"Starting API server on {api_host}:{api_port}...")
    api_cmd = [
        sys.executable, '-m', 'uvicorn',
        'api:app',
        '--host', api_host,
        '--port', str(api_port),
        '--log-level', 'info'
    ]
    
    api_process = subprocess.Popen(
        api_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Stream API output
    api_stream_thread = stream_output(api_process, print_api, "API")
    print_api(f"API server started (PID: {api_process.pid})")
    
    # Wait for API to be ready (optional)
    if wait_for_api_ready:
        if not wait_for_api('localhost', api_port):
            print_error("Failed to start API server")
            if api_process:
                api_process.terminate()
            sys.exit(1)
    else:
        print_info("Waiting 3 seconds for API server to initialize...")
        time.sleep(3)
    
    print()
    
    # Start monitor as subprocess
    print_monitor("Starting patient form monitor...")
    monitor_cmd = [sys.executable, 'monitor_patient_form.py']
    
    monitor_process = subprocess.Popen(
        monitor_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Stream monitor output
    monitor_stream_thread = stream_output(monitor_process, print_monitor, "Monitor")
    print_monitor(f"Monitor started (PID: {monitor_process.pid})")
    
    print()
    print("=" * 70)
    print_info("Both services are running!")
    print()
    print_info(f"📡 API Server: http://localhost:{api_port}")
    print_info(f"📡 API Docs: http://localhost:{api_port}/docs")
    print_info(f"🔍 Monitor: Watching for patient form submissions")
    print()
    print_info("Press Ctrl+C to stop both services")
    print("=" * 70)
    print()
    
    # Monitor both processes
    try:
        while True:
            # Check if processes are still alive
            if api_process and api_process.poll() is not None:
                print_error("API server process died unexpectedly")
                if monitor_process:
                    monitor_process.terminate()
                sys.exit(1)
            
            if monitor_process and monitor_process.poll() is not None:
                print_error("Monitor process died unexpectedly")
                if api_process:
                    api_process.terminate()
                sys.exit(1)
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == '__main__':
    main()

