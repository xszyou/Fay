"""
基于聚类的记忆抑制机制
实现从短期记忆中加载数倍目标条数，进行k-means聚类，每簇取最相似的代表

主要思路：
1. 从短期记忆中加载数倍(t:聚类平均条数)目标所需条数(k*n：从n倍的检索结果中取topk)的相关记录（含embedding），总检索条数=t*k*n
2. 对结果根据embedding进行k-means聚类，簇数为k*n（同条数/t）
3. 每簇取与检索最相似的代表当前簇，返回k个簇代表作为最终结果
"""

import numpy as np
from sklearn.cluster import KMeans
from typing import List, Dict, Tuple
import logging

# 使用统一日志配置
from bionicmemory.utils.logging_config import get_logger
logger = get_logger(__name__)

class ClusteringSuppression:
    """
    聚类抑制机制
    通过k-means聚类对相似记忆进行分组，从每组中选择最相关的代表
    """
    
    def __init__(self, 
                 cluster_multiplier: int = 3,
                 retrieval_multiplier: int = 2):
        """
        初始化聚类抑制机制
        
        Args:
            cluster_multiplier: 每个簇期望包含的记录数量，默认3条
            retrieval_multiplier: 检索结果倍数，默认2倍
        """
        self.cluster_multiplier = cluster_multiplier
        self.retrieval_multiplier = retrieval_multiplier
        logger.info(f"聚类抑制机制初始化: 每簇期望记录数={cluster_multiplier}, 检索倍数={retrieval_multiplier}")
    
    

    
    
    
    
    def calculate_retrieval_parameters(self, target_k: int) -> Tuple[int, int]:
        """
        计算检索参数
        
        Args:
            target_k: 目标返回条数
            
        Returns:
            (总检索条数, 聚类数)
        """
        # 聚类数 = 目标条数 * 检索倍数
        cluster_count = target_k * self.retrieval_multiplier
        
        # 总检索条数 = 聚类数 * 每簇期望记录数
        total_retrieval = cluster_count * self.cluster_multiplier
        
        return total_retrieval, cluster_count
    
    def cluster_by_query_similarity_and_aggregate(self,
                                                records: List[Dict],
                                                embeddings_array: np.ndarray,
                                                distances: List[float],
                                                cluster_count: int,
                                                target_k: int) -> List[Dict]:
        """
        基于查询相似度的聚类：
        - 簇内选与查询distance最小的记录为代表；
        - 代表记录的valid_access_count = 簇内所有记录的valid_access_count之和；
        - 最终结果 = 分别按相关度与valid_access_count各取target_k条，按doc_id去重后返回合集。
        Args:
            records: 与embeddings_array、distances一一对齐的记录列表（每条含embedding、distance、valid_access_count）
            embeddings_array: 形如 (N, D) 的向量数组
            distances: 长度为 N 的距离列表（越小越相似）
            cluster_count: 聚类簇数
            target_k: 返回前k条代表
        """
        import numpy as np
        from sklearn.cluster import KMeans

        if not isinstance(cluster_count, int) or cluster_count < 1:
            cluster_count = 1

        n = len(records)
        if n == 0:
            return []

        # 样本数 <= 聚类数：不聚类，直接在原集合上做双路topK并去重
        if n <= cluster_count:
            base = []
            for i in range(n):
                rep = dict(records[i])
                rep["cluster_size"] = 1
                base.append(rep)
            # 分别取topK
            by_rel = sorted(base, key=lambda x: float(x.get("distance", float("inf"))))[:target_k]
            by_cnt = sorted(base, key=lambda x: float(x.get("valid_access_count", 0.0)), reverse=True)[:target_k]
            # 合并去重（按doc_id）
            seen = set()
            merged = []
            for r in by_rel + by_cnt:
                rid = r.get("doc_id")
                if rid not in seen:
                    seen.add(rid)
                    merged.append(r)
            return merged

        # KMeans 聚类
        kmeans = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings_array)

        # 簇代表选择与累计
        representatives = []
        for cid in np.unique(labels):
            idx = np.where(labels == cid)[0]
            if len(idx) == 0:
                continue

            # 代表：簇内与查询distance最小
            local_dist = [(i, float(distances[i]) if distances[i] is not None else float("inf")) for i in idx]
            rep_idx, _ = min(local_dist, key=lambda t: t[1])

            # 累计簇内valid_access_count
            sum_valid = float(sum(float(records[i].get("valid_access_count", 0.0)) for i in idx))

            rep = dict(records[rep_idx])
            rep["valid_access_count"] = sum_valid
            rep["cluster_size"] = len(idx)
            representatives.append(rep)

        # 分别按相关度与valid_access_count取topK，然后合并去重
        top_by_relevance = sorted(representatives, key=lambda x: float(x.get("distance", float("inf"))))[:target_k]
        top_by_count = sorted(representatives, key=lambda x: float(x.get("valid_access_count", 0.0)), reverse=True)[:target_k]

        seen_ids = set()
        final_selection = []
        for r in top_by_relevance + top_by_count:
            rid = r.get("doc_id")
            if rid not in seen_ids:
                seen_ids.add(rid)
                final_selection.append(r)

        return final_selection