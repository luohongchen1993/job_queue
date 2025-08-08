#!/bin/bash

echo "=== previous jobs begin ==="
tail /root/experiments/job_queue/jobs.log
echo "=== previous jobs end ==="

# 解析参数
target_pid="$1"
shift
post_command="$@"

if [[ -z "$target_pid" || -z "$post_command" ]]; then
  echo "Usage: $0 <pid_to_wait_for> <command_to_run_after_pid_exits>"
  exit 1
fi

# 在子进程中执行主逻辑
(
  echo "[wait_then_run.sh] Started to wait for PID $target_pid"

  # 等待目标进程结束
  while kill -0 "$target_pid" 2>/dev/null; do
    sleep 1
  done

  echo "[wait_then_run.sh] PID $target_pid has exited. Running command: $post_command"
  eval "$post_command"
) &

# 输出这个 watcher 脚本本身的 PID
watcher_pid=$!
echo "[wait_then_run.sh] wait PID: $target_pid | job PID: $watcher_pid | job command: $post_command"
# also dump to log file
echo "[wait_then_run.sh] wait PID: $target_pid | job PID: $watcher_pid | job command: $post_command" >> /root/experiments/job_queue/jobs.log 2>&1

# can put in ~/.bashrc
# wait_then_run() {
#  bash /root/experiments/job_queue/run_job.sh "$@"
# }

