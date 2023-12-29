from typing import List, Dict, Any

def convert_to_float(value):
    if isinstance(value, str):
        if value == '非常高':
            return 1.0
        elif value == '高':
            return 0.8
        elif value == '中':
            return 0.5
        elif value == '低':
            return 0.0
        else:
            return 0.0
    else:
        return float(value)