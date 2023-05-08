import math

from typing import List, Tuple
from ..core.message_context import ChatGPTMessageContext

def euclidean_distance(a, b):
    return abs(a - b)

def dbscan(messages:List[ChatGPTMessageContext], eps, min_samples) ->List[List[ChatGPTMessageContext]]:
    clusters = []
    visited = set()

    for message in messages:
        if message in visited:
            continue

        visited.add(message)

        neighbors = [neighbor for neighbor in messages if euclidean_distance(neighbor.timestamp, message.timestamp) <= eps]

        if len(neighbors) < min_samples:
            continue

        cluster = [message]
        for neighbor in neighbors:
            if neighbor not in visited:
                visited.add(neighbor)

                new_neighbors = [new_neighbor for new_neighbor in messages if euclidean_distance(new_neighbor.timestamp, neighbor.timestamp) <= eps]
                if len(new_neighbors) >= min_samples:
                    neighbors.extend(new_neighbors)

                not_in_cluster = all([neighbor not in existing_cluster for existing_cluster in clusters])
                if not_in_cluster:
                    cluster.append(neighbor)

        clusters.append(cluster)

    return clusters

def find_most_recent_cluster(clusters:List[List[ChatGPTMessageContext]])->List[ChatGPTMessageContext]:
    most_recent_cluster = max(clusters, key=lambda cluster: max([message.timestamp for message in cluster]))
    return most_recent_cluster

def scale_to_reverse_exponential(value, min_factor, max_factor, lower_bound, upper_bound):
    """用于计算一个与value相关的因子(factor)。当value大于upper_bound时，factor取min_factor；当value小于lower_bound时，factor取max_factor。此外，随着value的减小，factor的增长速度指数加快。"""
    if value >= upper_bound:
        return min_factor
    elif value <= lower_bound:
        return max_factor
    else:
        # 指数关系的计算方式，其中a为自定义常数，调整指数关系的强度
        a = 5
        normalized_value = (value - lower_bound) / (upper_bound - lower_bound)
        factor = min_factor + (max_factor - min_factor) * (1 - math.exp(-a * (1 - normalized_value)))
        return factor