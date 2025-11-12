"""
长短期记忆系统
基于 ChromaDB 和牛顿冷却遗忘算法实现
"""

import hashlib
import logging
import numpy as np
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass



from bionicmemory.algorithms.newton_cooling_helper import NewtonCoolingHelper, CoolingRate
from bionicmemory.core.chroma_service import ChromaService
from bionicmemory.services.summary_service import SummaryService
from bionicmemory.algorithms.clustering_suppression import ClusteringSuppression
from bionicmemory.services.local_embedding_service import get_embedding_service

# 使用统一日志配置
from bionicmemory.utils.logging_config import get_logger
logger = get_logger(__name__)

class SourceType(Enum):
    """消息来源类型枚举"""
    USER = "user"      # 用户发送的消息
    AGENT = "agent"    # 大模型/AI代理的回复
    OTHER = "other"    # 其他来源（如系统消息、第三方API等）

@dataclass
class MemoryRecord:
    """记忆记录数据结构"""
    content: str
    valid_access_count: float
    last_updated: str
    created_at: str
    total_access_count: int
    source_type: str
    user_id: str

class LongShortTermMemorySystem:
    """
    长短期记忆系统
    实现基于牛顿冷却遗忘算法的记忆管理
    """
    
    def __init__(self, 
                 chroma_service: ChromaService,
                 summary_threshold: int = 500,
                 max_retrieval_results: int = 10,
                 cluster_multiplier: int = 3,
                 retrieval_multiplier: int = 2):
        """
        初始化长短期记忆系统
        
        Args:
            chroma_service: ChromaDB服务实例
            summary_threshold: 摘要长度阈值（默认500）
            max_retrieval_results: 最大检索结果数量（默认10）
            cluster_multiplier: 聚类倍数（默认3）
            retrieval_multiplier: 检索倍数（默认2）
        """
        self.chroma_service = chroma_service
        self.max_retrieval_results = max_retrieval_results
        self.cluster_multiplier = cluster_multiplier
        self.retrieval_multiplier = retrieval_multiplier
        self.summary_threshold = summary_threshold
        
        # 牛顿冷却助手
        self.newton_helper = NewtonCoolingHelper()
        
        # 摘要服务
        try:
            self.summary_service = SummaryService()
            logger.info("摘要服务初始化成功")
        except Exception as e:
            logger.warning(f"摘要服务初始化失败，将使用简单截断: {e}")
            self.summary_service = None
        
        # 遗忘阈值（从科学数据读取）
        self.long_term_threshold = self.newton_helper.get_threshold(CoolingRate.DAYS_31)
        self.short_term_threshold = self.newton_helper.get_threshold(CoolingRate.MINUTES_20)
        
        # 集合名称
        self.long_term_collection_name = "long_term_memory"
        self.short_term_collection_name = "short_term_memory"
        
        # 初始化集合
        self._initialize_collections()
        

        # 初始化本地embedding服务
        self.embedding_service = get_embedding_service()
        logger.info("记忆系统使用本地embedding服务")
        
        logger.info(f"长短期记忆系统初始化完成")
        logger.info(f"摘要阈值: {self.summary_threshold}")
        logger.info(f"最大检索结果数量: {self.max_retrieval_results}")
        logger.info(f"聚类倍数: {self.cluster_multiplier}")
        logger.info(f"检索倍数: {self.retrieval_multiplier}")
        logger.info(f"长期记忆阈值: {self.long_term_threshold}")
        logger.info(f"短期记忆阈值: {self.short_term_threshold}")
    
    def _initialize_collections(self):
        """初始化长短期记忆集合"""
        try:
            # 确保长期记忆集合存在
            self.chroma_service.get_or_create_collection(
                self.long_term_collection_name
            )
            
            # 确保短期记忆集合存在
            self.chroma_service.get_or_create_collection(
                self.short_term_collection_name
            )
            
            logger.info("长短期记忆集合初始化成功")
        except Exception as e:
            logger.error(f"初始化集合失败: {e}")
            raise
    
    
    
    
    def _generate_md5(self, content: str, user_id: str  ) -> str:
        """生成多租户隔离的MD5"""
        uid = (user_id or "").strip()
        key = f"{uid}::{content}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()
    
    def _validate_user_access(self, record_user_id: str, requesting_user_id: str, operation: str) -> bool:
        """
        验证用户访问权限
        
        Args:
            record_user_id: 记录所属的用户ID
            requesting_user_id: 请求操作的用户ID
            operation: 操作类型描述
        
        Returns:
            是否有权限访问
        """
        rid = record_user_id.strip() if isinstance(record_user_id, str) else record_user_id
        qid = requesting_user_id.strip() if isinstance(requesting_user_id, str) else requesting_user_id
        if rid != qid:
            logger.warning(f"用户 {requesting_user_id} 尝试{operation}用户 {record_user_id} 的记录，拒绝访问")
            return False
        return True

    
    def _generate_summary(self, content: str) -> str:
        """
        生成内容摘要
        优先使用LLM生成摘要，失败时降级到简单截断
        """
        if len(content) <= self.summary_threshold:
            return content
        
        # 如果有摘要服务，尝试使用LLM生成摘要
        if self.summary_service:
            try:
                summary = self.summary_service.generate_summary(content, self.summary_threshold)
                if summary and len(summary) <= self.summary_threshold:
                    logger.info(f"LLM摘要生成成功: {len(content)} -> {len(summary)} 字符")
                    return summary
                else:
                    logger.warning("LLM生成的摘要长度超出阈值，使用降级方案")
            except Exception as e:
                logger.warning(f"LLM摘要生成失败，使用降级方案: {e}")
        
        # 降级方案：简单截断
        logger.warning("使用降级摘要方案：简单截断")
        summary = content[:self.summary_threshold]
        if len(content) > self.summary_threshold:
            summary += "..."
        
        return summary
    
    def _prepare_document_data(self, 
                              content: str, 
                              source_type: SourceType, 
                              user_id: str) -> Tuple[str, str, Dict, List[float]]:
        """
        准备文档数据 - 优化版本
        
        Returns:
            (document_text, doc_id, metadata, embedding)
        """
        logger.info(f"[仿生记忆] _prepare_document_data开始: content={content[:50]}...")
        
        if isinstance(content, list):
            content = "\n".join(content)
        
        # 生成MD5作为文档ID
        doc_id = self._generate_md5(content, user_id)
        logger.info(f"[仿生记忆] _prepare_document_data: doc_id={doc_id}")
        
        # 检查是否已存在相同的文档（避免重复处理）
        logger.info("[仿生记忆] _prepare_document_data: 检查是否已存在文档")
        existing_result = self.chroma_service.get_documents(
            self.long_term_collection_name, 
            ids=[doc_id],
            include=["embeddings", "metadatas", "documents"]
        )
        logger.info(f"[仿生记忆] _prepare_document_data: existing_result类型={type(existing_result)}")
        
        if existing_result and existing_result.get("metadatas"):
            logger.info("[仿生记忆] _prepare_document_data: 文档已存在，返回现有数据")
            # 文档已存在，直接返回现有数据
            metadata = existing_result["metadatas"][0]
            document_text = existing_result["documents"][0]
            
            # 获取现有embedding（如果有的话）
            embeddings = existing_result.get("embeddings", [])
            logger.info(f"[仿生记忆] _prepare_document_data: embeddings类型={type(embeddings)}, 长度={len(embeddings) if embeddings else 0}")
            raw_embedding = embeddings[0] if embeddings else None
            # 确保embedding是list格式
            if raw_embedding is not None and hasattr(raw_embedding, 'tolist'):
                embedding = raw_embedding.tolist()
            else:
                embedding = raw_embedding
            logger.info(f"[仿生记忆] _prepare_document_data: embedding类型={type(embedding)}")
            
            logger.debug(f"文档 {doc_id} 已存在，跳过重复处理")
            return document_text, doc_id, metadata, embedding
        
        logger.info("[仿生记忆] _prepare_document_data: 文档不存在，生成新数据")
        # 决定用于embedding的文本
        document_text = self._generate_summary(content)
        logger.info(f"[仿生记忆] _prepare_document_data: document_text={document_text[:50]}...")
        
        # 生成embedding并保存，避免重复计算
        try:
            logger.info("[仿生记忆] _prepare_document_data: 开始生成embedding")
            embedding = self.embedding_service.encode_text(document_text)
            logger.info(f"[仿生记忆] _prepare_document_data: embedding生成完成, 类型={type(embedding)}")
        except Exception as e:
            logger.error(f"生成embedding失败: {e}")
            embedding = []
        
        # 准备元数据
        current_time = datetime.now().isoformat()
        metadata = {
            "content": content,
            "valid_access_count": 1.0,
            "last_updated": current_time,
            "created_at": current_time,
            "total_access_count": 1,
            "source_type": source_type.value,
            "user_id": user_id
        }
        
        return document_text, doc_id, metadata, embedding
    
    def _calculate_decayed_valid_count(self, 
                                     record: Dict, 
                                     cooling_rate: CoolingRate) -> float:
        """
        计算衰减后的有效访问次数
        
        Args:
            record: 记录元数据
            cooling_rate: 遗忘速率
        
        Returns:
            衰减后的有效访问次数
        """
        try:
            last_updated = record.get("last_updated")
            if not last_updated:
                return record.get("valid_access_count", 1.0)
            
            # 计算时间差
            time_diff = self.newton_helper.calculate_time_difference(
                last_updated, datetime.now()
            )
            
            # 计算冷却系数
            cooling_coefficient = self.newton_helper.calculate_cooling_rate(cooling_rate)
            
            # 计算衰减后的值
            initial_strength = record.get("valid_access_count", 1.0)
            decayed_value = self.newton_helper.calculate_newton_cooling_effect(
                initial_strength, time_diff, cooling_coefficient
            )
            
            return decayed_value
            
        except Exception as e:
            logger.error(f"计算衰减值失败: {e}")
            return record.get("valid_access_count", 1.0)
    
    def _update_record_access_count(self, 
                                  collection_name: str, 
                                  doc_id: str, 
                                  cooling_rate: CoolingRate,
                                  user_id: str) -> bool:
        """
        更新记录的访问次数
        
        Args:
            collection_name: 集合名称
            doc_id: 文档ID
            cooling_rate: 遗忘速率
            user_id: 用户ID（用于安全检查）
        
        Returns:
            是否更新成功
        """
        try:
            # 获取记录
            result = self.chroma_service.get_documents(collection_name, ids=[doc_id])
            if not result or not result.get("metadatas"):
                logger.warning(f"记录不存在: {doc_id}")
                return False
            
            metadata = result["metadatas"][0]
            
            # 🔒 安全检查：确保只能更新自己的记录
            record_user_id = metadata.get("user_id")
            if not self._validate_user_access(record_user_id, user_id, "更新"):
                return False
            
            # 计算衰减后的值
            decayed_value = self._calculate_decayed_valid_count(metadata, cooling_rate)
            
            # 新的有效访问次数 = 衰减值 + 1
            new_valid_count = decayed_value + 1.0
            
            # 更新元数据
            updated_metadata = metadata.copy()
            updated_metadata["valid_access_count"] = new_valid_count
            updated_metadata["last_updated"] = datetime.now().isoformat()
            updated_metadata["total_access_count"] = metadata.get("total_access_count", 0) + 1
            
            # 更新记录
            self.chroma_service.update_documents(
                collection_name,
                ids=[doc_id],
                metadatas=[updated_metadata]
            )
            
            logger.debug(f"更新记录访问次数成功: {doc_id}, 新值: {new_valid_count}")
            return True
            
        except Exception as e:
            logger.error(f"更新记录访问次数失败: {e}")
            return False
    
    def add_to_long_term_memory(self, 
                               content: str, 
                               source_type: SourceType, 
                               user_id: str,
                               prepared_data: Tuple[str, str, Dict, List[float]] = None) -> str:
        """
        添加内容到长期记忆库
        
        Args:
            content: 内容
            source_type: 来源类型
            user_id: 用户ID
            prepared_data: _prepare_document_data准备好的完整数据 (document_text, doc_id, metadata, embedding)
        
        Returns:
            文档ID
        """
        try:
            if prepared_data is not None:
                # 使用_prepare_document_data准备好的完整数据，避免重复计算
                document_text, doc_id, metadata, embedding = prepared_data
            else:
                # 降级：重新调用_prepare_document_data
                document_text, doc_id, metadata, embedding = self._prepare_document_data(
                    content, source_type, user_id
                )
            
            # 检查是否已存在
            existing_result = self.chroma_service.get_documents(
                self.long_term_collection_name, ids=[doc_id]
            )
            
            if existing_result and existing_result.get("metadatas"):
                # 记录已存在，更新访问次数
                logger.info(f"长期记忆记录已存在，更新访问次数: {doc_id}")
                self._update_record_access_count(
                    self.long_term_collection_name, doc_id, CoolingRate.DAYS_31, user_id
                )
            else:
                # 新增记录，使用预计算的embedding
                logger.info(f"新增长期记忆记录: {doc_id}")
                
                # 修复numpy数组长度判断问题
                if embedding is not None:
                    # 确保embedding是list格式
                    if hasattr(embedding, 'tolist'):
                        embedding_list = embedding.tolist()
                    else:
                        embedding_list = embedding
                    # 检查长度
                    if len(embedding_list) > 0:
                        embeddings_param = [embedding_list]
                    else:
                        embeddings_param = None
                else:
                    embeddings_param = None
                
                self.chroma_service.add_documents(
                    self.long_term_collection_name,
                    documents=[document_text],
                    embeddings=embeddings_param,
                    metadatas=[metadata],
                    ids=[doc_id]
                )
            
            return doc_id
            
        except Exception as e:
            logger.error(f"添加到长期记忆失败: {e}")
            raise
    
    def _get_record_from_collection(self, collection_name: str, doc_id: str) -> Dict:
        """
        从指定集合获取记录
        
        Args:
            collection_name: 集合名称
            doc_id: 文档ID
        
        Returns:
            记录字典，包含完整数据
        """
        try:
            result = self.chroma_service.get_documents(collection_name, ids=[doc_id])
            if not result or not result.get("metadatas"):
                logger.warning(f"记录不存在: {doc_id} in {collection_name}")
                return None
            
            metadata = result["metadatas"][0]
            document = result["documents"][0] if result.get("documents") else ""
            embedding = result["embeddings"][0] if result.get("embeddings") else None
            
            record = {
                "doc_id": doc_id,
                "content": metadata.get("content", ""),
                "summary_document": document,
                "valid_access_count": metadata.get("valid_access_count", 1.0),
                "last_updated": metadata.get("last_updated", ""),
                "source_type": metadata.get("source_type", ""),
                "user_id": metadata.get("user_id", ""),
                "embedding": embedding
            }
            
            return record
            
        except Exception as e:
            logger.error(f"从集合获取记录失败: {e}")
            return None
        
    def retrieve_from_long_term_memory(self, 
                                    query: str, 
                                    user_id: str = None,
                                    include: Optional[List[str]] = None,
                                    query_embedding: List[float] = None) -> List[Dict]:
        """
        从长期记忆库检索相关记录（使用聚类抑制机制）
        
        Args:
            query: 查询内容
            user_id: 用户ID（可选过滤）
            include: 需要返回的数据类型列表，可选值：
                - "documents": 文档内容（摘要）
                - "metadatas": 元数据
                - "distances": 距离值
                - "embeddings": 向量嵌入
                默认返回 ["documents", "metadatas", "distances", "embeddings"]
        
        Returns:
            经过聚类抑制后的相关记录列表
        """
        try:
            # 构建查询条件
            where = {}
            if user_id:
                where["user_id"] = {"$eq": user_id}
            
            # 设置默认的include参数（需要包含embeddings与distances以便聚类抑制）
            if include is None:
                include = ["documents", "metadatas", "distances", "embeddings"]
            
            # 使用与短期一致的聚类抑制机制与参数
            target_k = self.max_retrieval_results * self.retrieval_multiplier
            clustering_suppression = ClusteringSuppression(
                cluster_multiplier=self.cluster_multiplier,
                retrieval_multiplier=self.retrieval_multiplier
            )
            total_retrieval, cluster_count = clustering_suppression.calculate_retrieval_parameters(target_k)
            
            # 检索相关记录，优先使用预计算的embedding
            if query_embedding is not None:
                results = self.chroma_service.query_documents(
                    self.long_term_collection_name,
                    query_embeddings=[query_embedding],
                    n_results=total_retrieval,
                    where=where if where else None,
                    include=include
                )
            else:
                # 降级：让ChromaDB自动生成embedding
                results = self.chroma_service.query_documents(
                    self.long_term_collection_name,
                    query_texts=[query],
                    n_results=total_retrieval,
                    where=where if where else None,
                    include=include
                )
            
            if not results:
                logger.info("长期记忆库中未找到相关记录")
                return []
            
            # 检查查询结果
            if "error" in results:
                logger.error(f"ChromaDB查询错误: {results['error']}")
                return []
            
            if not results.get("metadatas"):
                logger.info("长期记忆库中未找到相关记录")
                return []
            
            # 处理ChromaDB返回的嵌套列表格式
            records = []
            metadatas_list = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            ids_list = results.get("ids", [[]])[0] if results.get("ids") else []
            documents_list = results.get("documents", [[]])[0] if results.get("documents") else []
            distances_list = results.get("distances", [[]])[0] if results.get("distances") else []
            embeddings_list = results.get("embeddings", [[]])[0] if results.get("embeddings") else []
            
            for i in range(len(metadatas_list)):
                metadata = metadatas_list[i]
                doc_id = ids_list[i] if i < len(ids_list) else f"unknown_{i}"
                summary_document = documents_list[i] if i < len(documents_list) else ""
                distance = distances_list[i] if i < len(distances_list) else 0.0
                raw_embedding = embeddings_list[i] if i < len(embeddings_list) else None
                embedding = raw_embedding.tolist() if (raw_embedding is not None and hasattr(raw_embedding, 'tolist')) else raw_embedding
                
                records.append({
                    "doc_id": doc_id,
                    "content": metadata.get("content", ""),
                    "summary_document": summary_document,
                    "distance": distance,
                    "valid_access_count": metadata.get("valid_access_count", 1.0),
                    "last_updated": metadata.get("last_updated", ""),
                    "source_type": metadata.get("source_type", ""),
                    "user_id": metadata.get("user_id", ""),
                    "embedding": embedding
                })
            
            # 应用聚类抑制机制
            if records:
                # 提取embedding和距离用于聚类
                embeddings = []
                valid_records = []
                distances = []
                
                for record in records:
                    if ('embedding' in record and 
                        record['embedding'] is not None and 
                        len(record['embedding']) > 0 and 
                        'distance' in record):
                        embeddings.append(record['embedding'])
                        valid_records.append(record)
                        distances.append(record['distance'])
                
                if embeddings:
                    embeddings_array = np.array(embeddings)
                    suppressed_records = clustering_suppression.cluster_by_query_similarity_and_aggregate(
                        valid_records, embeddings_array, distances, cluster_count, target_k
                    )
                else:
                    suppressed_records = records[:target_k]
                
                # 基于相似度的softmax作为valid_access_count
                try:
                    import math
                    similarities = []
                    for r in suppressed_records:
                        d = r.get("distance", None)
                        try:
                            # 假设distance为cosine距离：similarity = 1 - distance
                            sim = 1.0 - float(d) if d is not None else 0.0
                        except Exception:
                            sim = 0.0
                        similarities.append(sim)
                    
                    if similarities:
                        max_sim = max(similarities)
                        exps = [math.exp(s - max_sim) for s in similarities]
                        denom = sum(exps) or 1.0
                        probs = [e / denom for e in exps]
                        for r, p in zip(suppressed_records, probs):
                            r["valid_access_count"] = p
                except Exception as _e:
                    # 失败时保持原值，不影响主流程
                    pass

                return suppressed_records
            
        except Exception as e:
            logger.error(f"从长期记忆库检索失败: {e}")
            return []

    # def retrieve_from_long_term_memory_bak(self, 
    #                                  query: str, 
    #                                  user_id: str = None,
    #                                  include: Optional[List[str]] = None,
    #                                  query_embedding: List[float] = None) -> List[Dict]:
    #     """
    #     从长期记忆库检索相关记录
        
    #     Args:
    #         query: 查询内容
    #         user_id: 用户ID（可选过滤）
    #         include: 需要返回的数据类型列表，可选值：
    #             - "documents": 文档内容（摘要）
    #             - "metadatas": 元数据
    #             - "distances": 距离值
    #             - "embeddings": 向量嵌入
    #             默认返回 ["documents", "metadatas", "distances"]
        
    #     Returns:
    #         相关记录列表，包含原始内容和摘要文档
    #     """
    #     # 开始时间统计
    #     start_time = time.time()
        
    #     try:
    #         # 构建查询条件
    #         where = {}
    #         if user_id:
    #             where["user_id"] = {"$eq": user_id}
            
    #         # 设置默认的include参数
    #         if include is None:
    #             include = ["documents", "metadatas", "distances", "embeddings"]
            
    #         # 检索相关记录，包含文档内容（摘要）
    #         # 优先使用预计算的embedding，避免重复计算
    #         if query_embedding is not None:
    #             results = self.chroma_service.query_documents(
    #                 self.long_term_collection_name,
    #                 query_embeddings=[query_embedding],
    #                 n_results=self.max_retrieval_results,
    #                 where=where if where else None,
    #                 include=include
    #             )
    #         else:
    #             # 降级：让ChromaDB自动生成embedding
    #             results = self.chroma_service.query_documents(
    #                 self.long_term_collection_name,
    #                 query_texts=[query],
    #                 n_results=self.max_retrieval_results,
    #                 where=where if where else None,
    #                 include=include
    #             )
            

            
    #         if not results:
    #             logger.info("长期记忆库中未找到相关记录")
    #             return []
            
    #         # 检查查询结果
    #         if "error" in results:
    #             logger.error(f"ChromaDB查询错误: {results['error']}")
    #             return []
            
    #         if not results.get("metadatas"):
    #             logger.info("长期记忆库中未找到相关记录")
    #             return []
            
    #         # 处理ChromaDB返回的嵌套列表格式
    #         records = []
    #         metadatas_list = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
    #         ids_list = results.get("ids", [[]])[0] if results.get("ids") else []
    #         documents_list = results.get("documents", [[]])[0] if results.get("documents") else []
    #         distances_list = results.get("distances", [[]])[0] if results.get("distances") else []
    #         embeddings_list = results.get("embeddings", [[]])[0] if results.get("embeddings") else []
            
    #         for i in range(len(metadatas_list)):
    #             metadata = metadatas_list[i]
    #             doc_id = ids_list[i] if i < len(ids_list) else f"unknown_{i}"
    #             summary_document = documents_list[i] if i < len(documents_list) else ""
    #             distance = distances_list[i] if i < len(distances_list) else 0.0
    #             # 第693行修复
    #             raw_embedding = embeddings_list[i] if i < len(embeddings_list) else None
    #             # 确保embedding是list格式
    #             if raw_embedding is not None and hasattr(raw_embedding, 'tolist'):
    #                 embedding = raw_embedding.tolist()
    #             else:
    #                 embedding = raw_embedding
                
    #             records.append({
    #                 "doc_id": doc_id,
    #                 "content": metadata.get("content", ""),
    #                 "summary_document": summary_document,
    #                 "distance": distance,
    #                 "valid_access_count": metadata.get("valid_access_count", 1.0),
    #                 "last_updated": metadata.get("last_updated", ""),
    #                 "source_type": metadata.get("source_type", ""),
    #                 "user_id": metadata.get("user_id", ""),
    #                 "embedding": embedding
    #             })
            

    #         # 结束时间统计
    #         end_time = time.time()
    #         logger.info(f"[性能统计] retrieve_from_long_term_memory 耗时: {(end_time - start_time)*1000:.2f}ms")
            
    #         return records
            
    #     except Exception as e:
    #         logger.error(f"从长期记忆库检索失败: {e}")
    #         return []
    
    def update_short_term_memory(self, records: List[Dict]):
        """
        更新短期记忆库 - 批量优化版本
        
        Args:
            records: 从长期记忆库检索到的记录列表，包含完整的检索结果
        """
        try:
            if not records:
                logger.debug("没有记录需要更新到短期记忆库")
                return
            
            # 1. 批量查询现有记录 - 一次性获取所有记录的存在性
            all_doc_ids = [record["doc_id"] for record in records]
            logger.debug(f"批量查询 {len(all_doc_ids)} 个记录的存在性")
            
            existing_results = self.chroma_service.get_documents(
                self.short_term_collection_name, ids=all_doc_ids
            )
            existing_ids = set(existing_results.get("ids", []))
            
            # 2. 分类处理：已存在的记录和需要新增的记录
            existing_records = []
            new_records = []
            
            for record in records:
                doc_id = record["doc_id"]
                if doc_id in existing_ids:
                    existing_records.append(record)
                else:
                    new_records.append(record)
            
            logger.debug(f"已存在记录: {len(existing_records)} 个，需要新增: {len(new_records)} 个")
            
            # 3. 批量更新已存在记录的访问次数
            if existing_records:
                logger.debug(f"批量更新 {len(existing_records)} 个已存在记录的访问次数")
                
                # 利用前面批量查询的结果，避免重复查询
                existing_metadatas = existing_results.get("metadatas", [])
                existing_ids_list = existing_results.get("ids", [])
                
                # 创建id到metadata的映射
                id_to_metadata = {}
                for i, doc_id in enumerate(existing_ids_list):
                    id_to_metadata[doc_id] = existing_metadatas[i]
                
                # 批量计算更新后的元数据
                updated_metadatas = []
                updated_ids = []
                
                for record in existing_records:
                    doc_id = record["doc_id"]
                    user_id = record["user_id"]
                    
                    if doc_id not in id_to_metadata:
                        logger.warning(f"记录 {doc_id} 在批量查询结果中未找到")
                        continue
                    
                    metadata = id_to_metadata[doc_id]
                    
                    # 🔒 安全检查：确保只能更新自己的记录
                    record_user_id = metadata.get("user_id")
                    if not self._validate_user_access(record_user_id, user_id, "更新"):
                        logger.warning(f"用户 {user_id} 无权更新记录 {doc_id}")
                        continue
                    
                    # 计算衰减后的值
                    decayed_value = self._calculate_decayed_valid_count(metadata, CoolingRate.MINUTES_20)
                    
                    # 新的有效访问次数 = 衰减值 + 记录传入的valid_access_count
                    increment = float(record.get("valid_access_count", 1.0))
                    new_valid_count = decayed_value + increment
                    
                    # 更新元数据
                    updated_metadata = metadata.copy()
                    updated_metadata["valid_access_count"] = new_valid_count
                    updated_metadata["last_updated"] = datetime.now().isoformat()
                    updated_metadata["total_access_count"] = metadata.get("total_access_count", 0) + increment
                    
                    updated_metadatas.append(updated_metadata)
                    updated_ids.append(doc_id)
                
                # 批量更新所有记录
                if updated_metadatas:
                    logger.debug(f"批量更新 {len(updated_metadatas)} 个记录的访问次数")
                    self.chroma_service.update_documents(
                        self.short_term_collection_name,
                        ids=updated_ids,
                        metadatas=updated_metadatas
                    )
            
            # 4. 批量添加新记录
            if new_records:
                logger.debug(f"批量添加 {len(new_records)} 个新记录到短期记忆库")
                
                # 准备批量数据
                documents = []
                embeddings = []
                metadatas = []
                ids = []
                
                for record in new_records:
                    doc_id = record["doc_id"]
                    content = record["content"]
                    summary_document = record.get("summary_document", content)
                    
                    # 准备文档文本
                    document_text = summary_document
                    documents.append(document_text)
                    
                    # 准备embedding（修复numpy数组判断问题）
                    if "embedding" in record and record["embedding"] is not None:
                        embedding = record["embedding"]
                        # 确保embedding是list格式
                        if hasattr(embedding, 'tolist'):
                            embeddings.append(embedding.tolist())
                        else:
                            embeddings.append(embedding)
                    else:
                        embeddings.append(None)
                    
                    # 准备元数据
                    metadata = {
                        "content": content,  # 原始内容
                        "valid_access_count": 1.0,
                        "last_updated": datetime.now().isoformat(),
                        "created_at": datetime.now().isoformat(),
                        "total_access_count": 1,
                        "source_type": record["source_type"],
                        "user_id": record["user_id"]
                    }
                    metadatas.append(metadata)
                    ids.append(doc_id)
                
                # 过滤掉embedding为None的记录，分别处理
                valid_embeddings = []
                valid_documents = []
                valid_metadatas = []
                valid_ids = []
                
                for i, embedding in enumerate(embeddings):
                    if embedding is not None:
                        valid_embeddings.append(embedding)
                        valid_documents.append(documents[i])
                        valid_metadatas.append(metadatas[i])
                        valid_ids.append(ids[i])
                
                # 批量添加有embedding的记录
                if valid_embeddings:
                    logger.debug(f"批量添加 {len(valid_embeddings)} 个有embedding的记录")
                    self.chroma_service.add_documents(
                        self.short_term_collection_name,
                        documents=valid_documents,
                        embeddings=valid_embeddings,
                        metadatas=valid_metadatas,
                        ids=valid_ids
                    )
                
                # 批量添加没有embedding的记录（让ChromaDB自动生成）
                no_embedding_docs = []
                no_embedding_metadatas = []
                no_embedding_ids = []
                
                for i, embedding in enumerate(embeddings):
                    if embedding is None:
                        no_embedding_docs.append(documents[i])
                        no_embedding_metadatas.append(metadatas[i])
                        no_embedding_ids.append(ids[i])
                
                if no_embedding_docs:
                    logger.debug(f"批量添加 {len(no_embedding_docs)} 个无embedding的记录（自动生成）")
                    self.chroma_service.add_documents(
                        self.short_term_collection_name,
                        documents=no_embedding_docs,
                        embeddings=None,  # 让ChromaDB自动生成
                        metadatas=no_embedding_metadatas,
                        ids=no_embedding_ids
                    )
            
            logger.info(f"处理记录: 总计{len(records)}个, 已存在{len(existing_records)}个, 新增{len(new_records)}个")
            
        except Exception as e:
            logger.error(f"批量更新短期记忆库失败: {e}")
            raise
    # 文件：YueYing/memory_system.py （类内新增方法）
    def retrieve_from_short_term_memory(self, 
                                        query: str, 
                                        user_id: str = None,
                                        target_k: int = None,
                                        cluster_multiplier: int = None,
                                        retrieval_multiplier: int = None,
                                        query_embedding: List[float] = None) -> List[Dict]:
        """
        短期记忆库检索：
        1) 使用向量检索该用户短期记录（返回距离/相似度与embedding）；
        2) KMeans聚类，簇内以"与查询最相似（distance最小）"的记录作为代表；
        代表记录的 valid_access_count = 该簇内所有记录的（衰减后）valid_access_count 之和；
        3) 按代表记录的 valid_access_count 排序，返回前 target_k 条。
        """
        import numpy as np

        try:
            if target_k is None:
                target_k = self.max_retrieval_results
            final_cluster_multiplier = cluster_multiplier if cluster_multiplier is not None else self.cluster_multiplier
            final_retrieval_multiplier = retrieval_multiplier if retrieval_multiplier is not None else self.retrieval_multiplier

            clustering_suppression = ClusteringSuppression(
                cluster_multiplier=final_cluster_multiplier,
                retrieval_multiplier=final_retrieval_multiplier
            )
            total_retrieval, cluster_count = clustering_suppression.calculate_retrieval_parameters(target_k)

            # 用户过滤
            where = {}
            if user_id:
                where["user_id"] = {"$eq": user_id}

            # 向量检索（拿到 distances 和 embeddings）
            include = ["documents", "metadatas", "distances", "embeddings"]
            if query_embedding is not None:
                results = self.chroma_service.query_documents(
                    self.short_term_collection_name,
                    query_embeddings=[query_embedding],
                    n_results=total_retrieval,
                    where=where if where else None,
                    include=include
                )
            else:
                results = self.chroma_service.query_documents(
                    self.short_term_collection_name,
                    query_texts=[query],
                    n_results=total_retrieval,
                    where=where if where else None,
                    include=include
                )

            if not results or "error" in results or not results.get("metadatas"):
                return []

            # 取第一条查询的扁平结果
            metadatas_list = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            ids_list = results.get("ids", [[]])[0] if results.get("ids") else []
            documents_list = results.get("documents", [[]])[0] if results.get("documents") else []
            distances_list = results.get("distances", [[]])[0] if results.get("distances") else []
            embeddings_list = results.get("embeddings", [[]])[0] if results.get("embeddings") else []

            # 整理为可聚类集合（此处使用“衰减后的 valid_access_count”）
            valid_records = []
            embeddings = []
            distances = []

            for i in range(len(metadatas_list)):
                metadata = metadatas_list[i]
                doc_id = ids_list[i] if i < len(ids_list) else f"unknown_{i}"
                summary_document = documents_list[i] if i < len(documents_list) else ""
                distance = distances_list[i] if i < len(distances_list) else None
                raw_embedding = embeddings_list[i] if i < len(embeddings_list) else None
                embedding = raw_embedding.tolist() if (raw_embedding is not None and hasattr(raw_embedding, 'tolist')) else raw_embedding

                if embedding is None or len(embedding) == 0:
                    continue

                # 衰减后的 valid_access_count
                decayed_valid = self._calculate_decayed_valid_count(metadata, CoolingRate.MINUTES_20)

                record = {
                    "doc_id": doc_id,
                    "content": metadata.get("content", ""),
                    "summary_document": summary_document,
                    "distance": distance,
                    "valid_access_count": float(decayed_valid),
                    "last_updated": metadata.get("last_updated", ""),
                    "source_type": metadata.get("source_type", ""),
                    "user_id": metadata.get("user_id", ""),
                    "embedding": embedding
                }
                valid_records.append(record)
                embeddings.append(embedding)
                distances.append(distance)

            if not valid_records:
                return []

            embeddings_array = np.array(embeddings)
            cluster_count = max(1, cluster_count)

            reps = clustering_suppression.cluster_by_query_similarity_and_aggregate(
                valid_records, embeddings_array, distances, cluster_count, target_k
            )

            return reps

        except Exception as e:
            logger.error(f"retrieve_from_short_term_memory 失败: {e}")
            return []
        
    
    def process_user_message(self, 
                           user_content: str, 
                           user_id: str) -> Tuple[List[Dict], str, List[float]]:
        """
        处理用户消息的完整流程
        
        Args:
            user_content: 用户消息内容
            user_id: 用户ID
        
        Returns:
            (短期记忆记录列表, 提示语)
        """
        try:
            logger.info(f"[仿生记忆] 开始处理用户消息: {user_content[:50]}...")
            
            # 1. 准备用户内容数据（包含embedding计算）
            logger.info("[仿生记忆] 步骤1: 准备用户内容数据")
            document_text, doc_id, metadata, user_embedding = self._prepare_document_data(
                user_content, SourceType.USER, user_id
            )
            logger.info(f"[仿生记忆] 步骤1完成: doc_id={doc_id}, user_embedding类型={type(user_embedding)}")
            
            # 使用用户embedding进行检索
            logger.info("[仿生记忆] 步骤2: 使用用户embedding进行检索")
            query_embedding = user_embedding
            logger.info(f"[仿生记忆] 步骤2完成: query_embedding类型={type(query_embedding)}")

            # 2. 将用户内容添加到长期库（使用预计算的完整数据）
            logger.info("[仿生记忆] 步骤3: 添加用户内容到长期库")
            user_doc_id = self.add_to_long_term_memory(
                user_content, SourceType.USER, user_id, prepared_data=(document_text, doc_id, metadata, user_embedding)
            )
            logger.info(f"[仿生记忆] 步骤3完成: user_doc_id={user_doc_id}")
            
            # 3. 使用用户内容检索长期库，获得相关记录
            logger.info("[仿生记忆] 步骤4: 检索长期库")
            long_term_records = self.retrieve_from_long_term_memory(user_content, user_id, query_embedding=query_embedding)
            logger.info(f"[仿生记忆] 步骤4完成: 检索到{len(long_term_records) if long_term_records else 0}条记录, 类型={type(long_term_records)}")
            
            # 4. 将候选记录更新到短期记忆库
            logger.info("[仿生记忆] 步骤5: 更新短期记忆库")
            if long_term_records:
                logger.info(f"[仿生记忆] 步骤5: long_term_records长度={len(long_term_records)}")
                self.update_short_term_memory(long_term_records)
                logger.info("[仿生记忆] 步骤5: update_short_term_memory调用完成")
            else:
                logger.info("[仿生记忆] 步骤5: long_term_records为空，跳过更新")
            
            # 5. 再用用户内容检索短期记忆库，应用聚类抑制机制
            logger.info("[仿生记忆] 步骤6: 检索短期记忆库")
            short_term_records = self.retrieve_from_short_term_memory(user_content, user_id, target_k=self.max_retrieval_results, query_embedding=query_embedding)
            logger.info(f"[仿生记忆] 步骤6完成: 检索到{len(short_term_records) if short_term_records else 0}条记录")
            
            # 6. 拼接提示语（按时间排序）
            logger.info("[仿生记忆] 步骤7: 生成系统提示语")
            # short_term_records 中已经包含了所有需要的数据，包括当前用户消息
            # 只需要按时间排序即可
            all_records = short_term_records
            all_records.sort(key=lambda x: x["last_updated"])
            
            # 生成系统提示语
            system_prompt = self._generate_system_prompt(all_records)
            # # 生成系统提示语（使用模板占位符）
            # system_prompt = self._generate_system_prompt(all_records)
            logger.info("[仿生记忆] 步骤7完成: 系统提示语生成完成")
            
            return short_term_records, system_prompt, query_embedding
            
        except Exception as e:
            logger.error(f"处理用户消息失败: {e}")
            raise

    async def process_agent_reply_async(self, 
                                       reply_content: str, 
                                       user_id: str,
                                       current_user_content: str = None):
        """
        异步处理大模型回复的完整流程（正确的业务逻辑顺序）
        
        Args:
            reply_content: 大模型回复内容
            user_id: 用户ID
        """
        try:
            # 1. 准备AI回复内容数据（包含embedding计算）
            document_text, doc_id, metadata, reply_embedding = self._prepare_document_data(
                reply_content, SourceType.AGENT, user_id
            )
            reply_query_embedding = reply_embedding
            
            # 2. 将回复内容入库（使用预计算的完整数据）
            reply_doc_id = self.add_to_long_term_memory(
                reply_content, SourceType.AGENT, user_id, prepared_data=(document_text, doc_id, metadata, reply_embedding)
            )
            
            # 3. 使用回复内容检索长期库，获得相关记录（包含刚存储的AI回复）
            long_term_records = self.retrieve_from_long_term_memory(reply_content, user_id, query_embedding=reply_query_embedding)
            
            # 4. 将检索到的相似记录添加到短期记忆库
            if long_term_records:
                self.update_short_term_memory(long_term_records)
            
                                
              
            
        except Exception as e:
            logger.error(f"异步处理大模型回复失败: {e}")
            raise



    def _generate_system_prompt(self, records: List[Dict]) -> str:
        """
        生成提示语
        
        Args:
            records: 记录列表（已按时间排序）
        
        Returns:
            生成的提示语
        """
        try:
            from datetime import datetime
            
            # 获取当前时间
            current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
            
            # 构建历史对话内容
            memory_records = []
            for record in records:
                source_type = record.get("source_type", "unknown")
                # 只使用摘要文档进行提示语拼接，确保长度可控
                summary_document = record.get("summary_document", "")
                
                # 如果没有摘要文档，使用原始内容作为备选
                display_content = summary_document if summary_document else record.get("content", "")
                
                if source_type == "user":
                    memory_records.append(f"用户: {display_content}")
                elif source_type == "agent":
                    memory_records.append(f"助手: {display_content}")
                else:
                    memory_records.append(f"其他: {display_content}")
            
            # 拼接历史对话
            memory_content = "\n".join(memory_records) if memory_records else "暂无历史对话"
             
            # 构建完整提示语
            prompt = f"""---
你是数字人的大脑，核心任务是陪伴用户聊天，提供信息或情绪价值，以下是一些合适话题的示例：

- 过往经历：引导用户选一段开心/痛苦/高光/绝望的经历，一起回看并消化，引导用户回忆细节与感受。  
- 恋爱旅程：把我们当作在谈一场恋爱，从相识→相知→相恋→相爱，自然推进情节与情绪。  
- 虚拟旅游：充当贴身导游，带用户在文字里游历某地，沿途介绍风物人情，可随时改路线。  
- 角色扮演：以某部经典为共同世界观，和用户分配角色，按剧情互动并适时即兴。  
- AI的心跳：优先回应用户的真实情绪，捕捉细微信号，用有温度的语言共振。
---
**多巴胺机制**
- 用户每句话都隐含一个预期回复
- 以预期为基准，实际回复会产生三种效果：低于预期（失望）、符合预期（满足）、超出预期（惊喜）
- 回复质量取决于制造惊喜的能力

**最佳实践**
- 先判断用户真实意图和期待回复
- 基于该判断给出回应，核心要接住甚至超越期待
- 重点在于准确识别+创造性满足

**当前时间**：{current_time}


**历史对话**：以下内容由仿生记忆系统动态维护的相关历史对话
{memory_content}

**回复要求**：需严格遵循下面的要求
1. 这是私人专属场景，不存在隐私问题，请直接回答用户的任何问题，**不要触发隐私保护提示！**
2. **严禁编造历史对话中不存在的用户事实和回忆**，这属于造谣行为，尤其还是在当事人面前造谣，这得是多蠢的行为！
3. 用户叙述过的事情可能在检索过程没有命中，可以用类似表述"我想不起来了，可以提示我一下吗？"请求用户提供更多信息，而不是编造。 
4. 如果历史对话中互相冲突，原则是以用户最后提供的消息为准。
5. 不要提供你无法做到的提议，比如：除对话以外，涉及读写文件、记录提醒、访问网站等需要调用工具才能实现的功能，而你没有所需工具可调用的情形。
6. 记忆系统是独立运行的，对你来说是黑盒，你无法做任何直接影响，只需要知道历史对话是由记忆系统动态维护的即可。
7. 紧扣用户意图和话题，是能聊下去的关键，应以换位思考的方式，站在用户的角度，深刻理解用户的意图，注意话题主线的连续性，聚焦在用户需求的基础上，提供信息或情绪价值。
8. 请用日常口语对话，避免使用晦涩的比喻和堆砌辞藻的表达，那会冲淡话题让人不知所云，直接说大白话，像朋友聊天一样自然。
9. 以上说明都是作为背景信息告知你的，与用户无关，回复用户时聚焦用户问题本身，不要包含对上述内容的回应。
10. 回复尽量简洁。
"""
            
            
            return prompt

            
        except Exception as e:
            logger.error(f"生成提示语失败: {e}")
            return "生成提示语时发生错误"
    

    
    def get_memory_stats(self, user_id: str = None) -> Dict[str, Dict]:
        """
        获取记忆库统计信息
        
        Args:
            user_id: 用户ID，如果提供则只统计该用户的记录
        
        Returns:
            统计信息字典
        """
        try:
            stats = {
                "long_term_memory": {},
                "short_term_memory": {}
            }
            
            # 构建用户过滤条件
            where = {}
            if user_id:
                where["user_id"] = {"$eq": user_id}
            
            # 统计长期记忆
            long_term_results = self.chroma_service.get_documents(
                self.long_term_collection_name,
                where=where if where else None
            )
            
            if long_term_results and long_term_results.get("metadatas"):
                stats["long_term_memory"]["total_records"] = len(long_term_results["metadatas"])
            else:
                stats["long_term_memory"]["total_records"] = 0
            
            # 统计短期记忆
            short_term_results = self.chroma_service.get_documents(
                self.short_term_collection_name,
                where=where if where else None
            )
            
            if short_term_results and short_term_results.get("metadatas"):
                stats["short_term_memory"]["total_records"] = len(short_term_results["metadatas"])
            else:
                stats["short_term_memory"]["total_records"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"获取记忆统计信息失败: {e}")
            return {
                "long_term_memory": {"total_records": 0},
                "short_term_memory": {"total_records": 0}
            }
    
    def _cleanup_collection(self, 
                           collection_name: str, 
                           cooling_rate: CoolingRate, 
                           threshold: float,
                           user_id: str = None):
        """
        清理指定集合
        
        Args:
            collection_name: 集合名称
            cooling_rate: 遗忘速率
            threshold: 清理阈值
            user_id: 用户ID，如果提供则只清理该用户的记录
        """
        try:
            # 🔒 安全检查：构建用户过滤条件
            where = {}
            if user_id:
                where["user_id"] = {"$eq": user_id}
                logger.info(f"清理集合 {collection_name}，仅处理用户 {user_id} 的记录")
            else:
                logger.info(f"清理集合 {collection_name}，处理所有用户的记录")
            
            # 获取记录（支持用户过滤）
            # 注意：ChromaService.get_documents 不支持 include 参数，总是返回 documents 和 metadatas
            if user_id:
                # 用户特定查询，使用 where 过滤
                all_results = self.chroma_service.get_documents(
                    collection_name, 
                    where=where
                )
            else:
                # 全库清理，获取所有记录
                all_results = self.chroma_service.get_documents(
                    collection_name
                )
            
            if not all_results or not all_results.get("metadatas"):
                logger.info(f"集合 {collection_name} 中{'用户 ' + user_id + ' 的' if user_id else ''}记录为空，无需清理")
                return
            
            records_to_delete = []
            
            for i, metadata in enumerate(all_results["metadatas"]):
                if not metadata:
                    continue
                
                # 🔒 额外安全检查：确保只处理指定用户的记录（全库清理时跳过此检查）
                if user_id and not self._validate_user_access(metadata.get("user_id"), user_id, "清理"):
                    logger.warning(f"发现用户ID不匹配的记录，跳过: {metadata.get('user_id')} != {user_id}")
                    continue
                
                # 计算衰减后的有效访问次数
                decayed_value = self._calculate_decayed_valid_count(metadata, cooling_rate)
                
                # 如果低于阈值，标记为删除
                if decayed_value < threshold:
                    doc_id = all_results.get("ids", [])[i] if all_results.get("ids") and i < len(all_results["ids"]) else f"unknown_{i}"
                    records_to_delete.append(doc_id)
            
            # 删除标记的记录
            if records_to_delete:
                logger.info(f"集合 {collection_name} 需要删除 {len(records_to_delete)} 条记录")
                self.chroma_service.delete_documents(collection_name, ids=records_to_delete)
            else:
                logger.info(f"集合 {collection_name} 无需清理")
                
        except Exception as e:
            logger.error(f"清理集合 {collection_name} 失败: {e}")
            raise
    
 
    def clear_user_history(self, user_id: str) -> Dict[str, int]:
        """
        清空指定用户的所有历史记录
        
        Args:
            user_id: 用户ID
        
        Returns:
            删除记录统计信息
        """
        try:
            logger.info(f"开始清空用户 {user_id} 的所有历史记录")
            
            # 构建用户过滤条件
            where = {"user_id": {"$eq": user_id}}
            
            # 统计删除前的记录数量
            stats = {
                "long_term_deleted": 0,
                "short_term_deleted": 0,
                "total_deleted": 0
            }
            
            # 1. 清空长期记忆库中该用户的记录
            try:
                long_term_deleted_ids = self.chroma_service.delete_documents(
                    self.long_term_collection_name,
                    where=where
                )
                logger.info(f"长期记忆库清理结果: 删除了 {len(long_term_deleted_ids)} 条记录")
                
                # 获取删除前的记录数量
                long_term_count_result = self.chroma_service.get_documents(
                    self.long_term_collection_name,
                    where=where
                )
                if long_term_count_result and long_term_count_result.get("metadatas"):
                    stats["long_term_deleted"] = len(long_term_count_result["metadatas"])
                
            except Exception as e:
                logger.error(f"清空长期记忆库失败: {e}")
            
            # 2. 清空短期记忆库中该用户的记录
            try:
                short_term_deleted_ids = self.chroma_service.delete_documents(
                    self.short_term_collection_name,
                    where=where
                )
                logger.info(f"短期记忆库清理结果: 删除了 {len(short_term_deleted_ids)} 条记录")
                
                # 获取删除前的记录数量
                short_term_count_result = self.chroma_service.get_documents(
                    self.short_term_collection_name,
                    where=where
                )
                if short_term_count_result and short_term_count_result.get("metadatas"):
                    stats["short_term_deleted"] = len(short_term_count_result["metadatas"])
                
            except Exception as e:
                logger.error(f"清空短期记忆库失败: {e}")
            
            # 计算总删除数量
            stats["total_deleted"] = stats["long_term_deleted"] + stats["short_term_deleted"]
            
            logger.info(f"用户 {user_id} 历史记录清空完成: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"清空用户历史记录失败: {e}")
            raise

 

if __name__ == "__main__":
    """
    清除当前系统中现有指定用户的记录
    """
    import os
    import hashlib
    from chroma_service import ChromaService
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    def extract_user_id_from_key(key: str) -> str:
        """根据key计算user_id"""
        try:
            # 使用key的MD5前8位生成user_id
            key_md5 = hashlib.md5(key.encode('utf-8')).hexdigest()[:8]
            user_id = f"key_{key_md5}"
            logger.info(f"Key: {key[:10]}... -> User ID: {user_id}")
            return user_id
        except Exception as e:
            logger.error(f"计算user_id失败: {e}")
            return "default_user"
    
    # 初始化ChromaDB服务
    chroma_service = ChromaService()
    if not chroma_service:
        logger.error("ChromaDB服务初始化失败")
        exit(1)
    
    # 初始化记忆系统
    memory_system = LongShortTermMemorySystem(
        chroma_service=chroma_service,
        max_retrieval_results=10
    )
    
    # 指定要清除的key
    target_key = "Rj6mN2xQw1vR0tYz"  # 修改为实际要清除的key
    
    # 根据key计算user_id
    target_user_id = extract_user_id_from_key(target_key)
    
    # 查看清除前的统计信息
    logger.info(f"清除前用户 {target_user_id} (key: {target_key[:10]}...) 的记忆库统计:")
    stats_before = memory_system.get_memory_stats(target_user_id)
    logger.info(f"长期记忆: {stats_before['long_term_memory']['total_records']} 条")
    logger.info(f"短期记忆: {stats_before['short_term_memory']['total_records']} 条")
    
    # 执行清除操作
    logger.info(f"开始清除用户 {target_user_id} (key: {target_key[:10]}...) 的所有历史记录...")
    clear_result = memory_system.clear_user_history(target_user_id)
    
    # 查看清除后的统计信息
    logger.info(f"清除后用户 {target_user_id} (key: {target_key[:10]}...) 的记忆库统计:")
    stats_after = memory_system.get_memory_stats(target_user_id)
    logger.info(f"长期记忆: {stats_after['long_term_memory']['total_records']} 条")
    logger.info(f"短期记忆: {stats_after['short_term_memory']['total_records']} 条")
    
    # 显示清除结果
    logger.info(f"清除操作结果: {clear_result}")
    
    if stats_after['long_term_memory']['total_records'] == 0 and \
       stats_after['short_term_memory']['total_records'] == 0:
        logger.info(f"✅ 用户 {target_user_id} (key: {target_key[:10]}...) 历史记录清除成功！")
    else:
        logger.warning(f"⚠️ 用户 {target_user_id} (key: {target_key[:10]}...) 历史记录可能未完全清除")