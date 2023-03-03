#!/bin/sh

zip -q -r amiyabot-hsyhhssyy-chatgpt-1.5.zip *
rm -rf ../../amiya-bot-v6/plugins/amiyabot-hsyhhssyy-chatgpt-*
mv amiyabot-hsyhhssyy-chatgpt-*.zip ../../amiya-bot-v6/plugins/
docker restart amiya-bot 