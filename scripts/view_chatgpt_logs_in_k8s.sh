#!/bin/bash

# 获取pod的最新2000行日志
kubectl logs amiya-bot-1-deployment-565d9755dc-nrs4l -n amiya-bot --tail=2000 > logs.txt

# 从中找到包含 "不知道他愿不愿意和我在一起" 这段内容的行及其前后200行
grep -C 200 "不知道他愿不愿意和我在一起" logs.txt > context.txt

# 打印结果
cat context.txt
