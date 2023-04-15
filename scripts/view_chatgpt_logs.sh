#!/bin/bash

# 检查参数数量
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <number_of_recent_records>"
  exit 1
fi

# 设置要查找的记录数量
number_of_records=$1

# 找到容器ID
container_id=$(docker inspect -f '{{.Id}}' amiya-bot)

# 设置日志文件路径
log_file_path="/var/lib/docker/containers/${container_id}/${container_id}-json.log"

# 如果找到了log文件
if [ ! -z "$log_file_path" ]; then
  echo "Log file found at: $log_file_path"
  # 提取所需的记录，并按照所需的格式输出
  grep "\[ ChatGPT\]" "$log_file_path" | tail -n "$number_of_records" | sed -r 's/^.*"log":"([^"]+)".*"time":"([^"]+)".*$/\1/'
else
  echo "Log file not found."
fi
