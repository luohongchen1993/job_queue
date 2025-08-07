#!/usr/bin/env python3

import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from job_queue import JobQueue

def main():
    parser = argparse.ArgumentParser(description='Job Queue CLI - Run scripts sequentially')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    add_parser = subparsers.add_parser('add', help='Add a job to the queue')
    add_parser.add_argument('script', help='Script or command to run')
    add_parser.add_argument('--name', help='Optional name for the job')
    
    status_parser = subparsers.add_parser('status', help='Show queue status')
    status_parser.add_argument('--job-id', help='Show details for specific job')
    
    remove_parser = subparsers.add_parser('remove', help='Remove a pending job')
    remove_parser.add_argument('job_id', help='Job ID to remove')
    
    stop_parser = subparsers.add_parser('stop', help='Stop a running job')
    stop_parser.add_argument('job_id', help='Job ID to stop')
    
    worker_parser = subparsers.add_parser('worker', help='Start the background worker')
    
    clear_parser = subparsers.add_parser('clear', help='Clear completed jobs')
    
    logs_parser = subparsers.add_parser('logs', help='Show recent logs')
    logs_parser.add_argument('--lines', type=int, default=20, help='Number of lines to show')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    jq = JobQueue()
    
    if args.command == 'add':
        job_id = jq.add_job(args.script, args.name)
        print(f"Added job {job_id}")
        
    elif args.command == 'status':
        if args.job_id:
            job = jq.get_job(args.job_id)
            if job:
                print(f"Job {job['id']}: {job['name']}")
                print(f"  Command: {job['command']}")
                print(f"  Status: {job['status']}")
                print(f"  Created: {job['created_at']}")
                if job['started_at']:
                    print(f"  Started: {job['started_at']}")
                if job['completed_at']:
                    print(f"  Completed: {job['completed_at']}")
                if job['exit_code'] is not None:
                    print(f"  Exit code: {job['exit_code']}")
                
                # Check for job log file
                log_path = jq.logs_dir / f"job_{job['id']}.log"
                if log_path.exists():
                    print(f"  Log file: {log_path}")
            else:
                print(f"Job {args.job_id} not found")
        else:
            jobs = jq.get_status()
            if not jobs:
                print("No jobs in queue")
                return
                
            print(f"{'ID':<8} {'Name':<20} {'Status':<10} {'Command'}")
            print("-" * 60)
            for job in jobs:
                name = job['name'][:18] + '..' if len(job['name']) > 20 else job['name']
                command = job['command'][:25] + '..' if len(job['command']) > 27 else job['command']
                print(f"{job['id']:<8} {name:<20} {job['status']:<10} {command}")
                
    elif args.command == 'remove':
        if jq.remove_job(args.job_id):
            print(f"Removed job {args.job_id}")
        else:
            print(f"Could not remove job {args.job_id} (not found or not pending)")
            
    elif args.command == 'stop':
        if jq.stop_job(args.job_id):
            print(f"Stopped job {args.job_id}")
        else:
            print(f"Could not stop job {args.job_id} (not found or not running)")
            
    elif args.command == 'worker':
        print("Starting job queue worker... Press Ctrl+C to stop")
        jq.start_worker()
        
    elif args.command == 'clear':
        jobs = jq.get_status()
        completed_jobs = [j for j in jobs if j['status'] in ['completed', 'failed']]
        pending_running = [j for j in jobs if j['status'] in ['pending', 'running']]
        
        jq._save_queue(pending_running)
        print(f"Cleared {len(completed_jobs)} completed/failed jobs")
        
    elif args.command == 'logs':
        if jq.log_file.exists():
            with open(jq.log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-args.lines:]:
                    print(line.strip())
        else:
            print("No logs found")

if __name__ == '__main__':
    main()