import sys
import os

if __package__:
    from .main import bot
else:
    sys.path.append(os.path.dirname(__file__))
    import main

if len(sys.argv)<2:
    print("请使用build或者test命令")
    exit()


cmd = sys.argv[1]

if cmd=="build":
    os.system(f'rm {bot.plugin_id}-*.zip')
    os.system(f'zip -q -r {bot.plugin_id}-{bot.version}.zip *')
else:
    os.system(f'rm {bot.plugin_id}-*.zip')
    os.system(f'zip -q -r {bot.plugin_id}-{bot.version}.zip *')
    os.system(f'rm -rf ../../amiya-bot-v6/plugins/{bot.plugin_id}-*')
    os.system(f'mv {bot.plugin_id}-*.zip ../../amiya-bot-v6/plugins/')
    os.system(f'docker restart amiya-bot')
    

