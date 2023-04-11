import sys
import os
import re

amiya_bot_plugin_path = "../../amiya-bot-v6/plugins"

if len(sys.argv)<2:
    print("请使用build或者test命令")
    exit()

def read_file(file_name):
    # 获取当前脚本所在的目录
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    # 将目录和文件名组合成文件路径
    file_path = os.path.join(curr_dir, file_name)

    # 检查文件是否存在
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return content
    else:
        print(f"文件 '{file_name}' 不存在.")
        return None

file_name = 'main.py'
content = read_file(file_name)

if not content:
    print('未找到main.py')

version_pattern = r"version='([\d.]+)'"
plugin_id_pattern = r"plugin_id='([\w-]+)'"

version_match = re.search(version_pattern, content)
plugin_id_match = re.search(plugin_id_pattern, content)

if not version_match or not plugin_id_match:
    print('未找到main.py下的配置项')
    exit

version = version_match.group(1)
plugin_id = plugin_id_match.group(1)

cmd = sys.argv[1]

if cmd=="build":
    os.system(f'rm {plugin_id}-*.zip')
    os.system(f'zip -q -r {plugin_id}-{version}.zip *')
else:
    os.system(f'rm {plugin_id}-*.zip')
    os.system(f'zip -q -r {plugin_id}-{version}.zip *')
    os.system(f'rm -rf {amiya_bot_plugin_path}/{plugin_id}-*')
    os.system(f'cp {plugin_id}-*.zip {amiya_bot_plugin_path}/')
    os.system(f'docker restart amiya-bot')
    

