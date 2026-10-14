#!/usr/bin/env python
import os
import sys
import subprocess

# Set the working directory
os.chdir(r'C:\Internship\Verxeon\CV Project\backend')

# Add to PYTHONPATH
sys.path.insert(0, os.getcwd())

# Start the uvicorn server
proc = subprocess.Popen([
    'python', '-m', 'uvicorn', 'app.main:app',
    '--host', '0.0.0.0',
    '--port', '8000',
    '--reload'
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

print(f"Server starting on http://0.0.0.0:8000")
print(f"PID: {proc.pid}")

# Print output periodically
import time
while proc.poll() is None:
    line = proc.stderr.readline()
    if line:
        print(line.strip())
    time.sleep(0.5)

print(f"Server process ended with code {proc.returncode}")