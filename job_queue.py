#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class JobQueue:
    def __init__(self, queue_file: str = "job_queue.json", log_file: str = "job_queue.log", logs_dir: str = "job_logs"):
        self.queue_file = Path(queue_file)
        self.log_file = Path(log_file)
        self.logs_dir = Path(logs_dir)
        self.lock = threading.Lock()
        self.running_processes = {}  # job_id -> process object
        
        # Create logs directory if it doesn't exist
        self.logs_dir.mkdir(exist_ok=True)
        
    def _load_queue(self) -> List[Dict]:
        if not self.queue_file.exists():
            return []
        try:
            with open(self.queue_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_queue(self, jobs: List[Dict]) -> None:
        with open(self.queue_file, 'w') as f:
            json.dump(jobs, f, indent=2)
    
    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        with open(self.log_file, 'a') as f:
            f.write(log_message)
        
        print(log_message.strip())
    
    def _write_job_log(self, job: Dict, stdout: str = "", stderr: str = "") -> None:
        job_id = job["id"]
        log_filename = f"job_{job_id}.log"
        log_path = self.logs_dir / log_filename
        
        with open(log_path, 'w') as f:
            f.write(f"Job ID: {job_id}\n")
            f.write(f"Name: {job['name']}\n")
            f.write(f"Command: {job['command']}\n")
            f.write(f"Status: {job['status']}\n")
            f.write(f"Created: {job['created_at']}\n")
            f.write(f"Started: {job['started_at']}\n")
            f.write(f"Completed: {job['completed_at']}\n")
            f.write(f"Exit Code: {job['exit_code']}\n")
            f.write(f"{'='*50}\n")
            
            if stdout:
                f.write("STDOUT:\n")
                f.write(stdout)
                f.write("\n")
            
            if stderr:
                f.write("STDERR:\n")
                f.write(stderr)
                f.write("\n")
    
    def add_job(self, command: str, name: Optional[str] = None) -> str:
        with self.lock:
            jobs = self._load_queue()
            
            job_id = str(uuid.uuid4())[:8]
            job = {
                "id": job_id,
                "name": name or f"Job {job_id}",
                "command": command,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "started_at": None,
                "completed_at": None,
                "exit_code": None,
                "pid": None,
                "stop_requested": False
            }
            
            jobs.append(job)
            self._save_queue(jobs)
            
            self._log(f"Added job {job_id}: {job['name']}")
            return job_id
    
    def get_status(self) -> List[Dict]:
        return self._load_queue()
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        jobs = self._load_queue()
        for job in jobs:
            if job["id"] == job_id:
                return job
        return None
    
    def remove_job(self, job_id: str) -> bool:
        with self.lock:
            jobs = self._load_queue()
            for i, job in enumerate(jobs):
                if job["id"] == job_id and job["status"] == "pending":
                    jobs.pop(i)
                    self._save_queue(jobs)
                    self._log(f"Removed job {job_id}")
                    return True
            return False
    
    def stop_job(self, job_id: str) -> bool:
        # Simply mark the job for stopping - let worker handle the actual killing
        job = self.get_job(job_id)
        if job and job["status"] in ["pending", "running"]:
            self._update_job(job_id, {"stop_requested": True})
            print(f"Stop requested for job {job_id}")
            return True
        return False
    
    def _update_job(self, job_id: str, updates: Dict) -> None:
        with self.lock:
            jobs = self._load_queue()
            for job in jobs:
                if job["id"] == job_id:
                    job.update(updates)
                    break
            self._save_queue(jobs)
    
    def run_next_job(self) -> bool:
        jobs = self._load_queue()
        
        for job in jobs:
            if job["status"] == "pending":
                job_id = job["id"]
                self._log(f"Starting job {job_id}: {job['name']}")
                
                self._update_job(job_id, {
                    "status": "running",
                    "started_at": datetime.now().isoformat()
                })
                
                try:
                    process = subprocess.Popen(
                        job["command"],
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # Store the process so it can be stopped
                    self.running_processes[job_id] = process
                    
                    # Store PID in job data for persistence
                    self._update_job(job_id, {"pid": process.pid})
                    
                    # Wait for completion while checking for stop requests
                    stdout = ""
                    stderr = ""
                    while process.poll() is None:  # While process is still running
                        # Check if stop was requested
                        current_job = self.get_job(job_id)
                        if current_job and current_job.get("stop_requested"):
                            # Kill the process immediately
                            pid = process.pid
                            subprocess.run(["pkill", "-KILL", "-P", str(pid)], check=False)
                            subprocess.run(["kill", "-KILL", str(pid)], check=False)
                            process.kill()
                            
                            # Remove from running processes
                            if job_id in self.running_processes:
                                del self.running_processes[job_id]
                            
                            self._update_job(job_id, {
                                "status": "stopped",
                                "completed_at": datetime.now().isoformat(),
                                "exit_code": -15,
                                "pid": None,
                                "stop_requested": False
                            })
                            
                            # Write log file
                            updated_job = self.get_job(job_id)
                            if updated_job:
                                self._write_job_log(updated_job, "", "Job was stopped by user")
                            
                            self._log(f"Stopped job {job_id}")
                            return True
                        
                        time.sleep(0.1)  # Check every 100ms
                    
                    # Process finished normally, get output
                    stdout, stderr = process.communicate()
                    exit_code = process.returncode
                    
                    # Remove from running processes
                    if job_id in self.running_processes:
                        del self.running_processes[job_id]
                    
                    self._update_job(job_id, {
                        "status": "completed",
                        "completed_at": datetime.now().isoformat(),
                        "exit_code": exit_code,
                        "pid": None
                    })
                    
                    # Get updated job data and write to log file
                    updated_job = self.get_job(job_id)
                    if updated_job:
                        self._write_job_log(updated_job, stdout, stderr)
                    
                    if exit_code == 0:
                        self._log(f"Job {job_id} completed successfully")
                    else:
                        self._log(f"Job {job_id} failed with exit code {exit_code}")
                    
                    return True
                    
                except Exception as e:
                    # Remove from running processes if it's there
                    if job_id in self.running_processes:
                        del self.running_processes[job_id]
                    
                    self._update_job(job_id, {
                        "status": "failed",
                        "completed_at": datetime.now().isoformat(),
                        "exit_code": -1,
                        "pid": None
                    })
                    
                    # Get updated job data and write to log file
                    updated_job = self.get_job(job_id)
                    if updated_job:
                        self._write_job_log(updated_job, "", str(e))
                    
                    self._log(f"Job {job_id} failed with exception: {e}")
                    return True
        
        return False
    
    def worker_loop(self) -> None:
        self._log("Worker started")
        while True:
            if not self.run_next_job():
                # Check for pending jobs that need to be cancelled
                jobs = self._load_queue()
                for job in jobs:
                    if job.get("stop_requested") and job["status"] == "pending":
                        self._update_job(job["id"], {
                            "status": "stopped",
                            "completed_at": datetime.now().isoformat(),
                            "exit_code": -1,
                            "stop_requested": False
                        })
                        self._log(f"Cancelled pending job {job['id']}")
                
                time.sleep(1)
    
    def start_worker(self) -> None:
        worker_thread = threading.Thread(target=self.worker_loop, daemon=True)
        worker_thread.start()
        self._log("Background worker started")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self._log("Worker stopped")