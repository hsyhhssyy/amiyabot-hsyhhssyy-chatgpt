import re

def format_text(input_text):
    # 定义正则表达式模式，用于提取所需的值
    pattern = r'\[cl (.*?)@#.*? cle\]'

    # 使用re.sub函数将格式化字符串替换为提取的值
    formatted_text = re.sub(pattern, lambda x: x.group(1), input_text)

    return formatted_text

# 测试函数
input_text = "攻击范围缩小，防御力+ [cl 100%@#174CC6 cle] ，每秒恢复最大生命的 [cl 0.06@#174CC6 cle] "
formatted_result = format_text(input_text)
print(formatted_result)