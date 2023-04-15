

from datetime import datetime

def calculate_timestamp_factor(time_a: float, time_b: float, max_factor=3.0, min_factor=1.0) -> float:
    if time_a is None or time_b is None:
        return min_factor

    # 计算时间差的绝对值（以秒为单位）
    time_diff = abs(time_b - time_a)

    time_threhold = 30

    # 将时间差映射到 factor 范围，例如 1 到 3
    # 当时间差为 0 时，factor 为 max_factor
    # 当时间差增加时，factor 值减小，趋近于 min_factor
    factor = max_factor - (max_factor - min_factor) * (time_diff / (time_diff + time_threhold))

    return factor