import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from typing import Optional, List, Dict, Any, Union, Callable
import json
import logging
import os
from dotenv import load_dotenv
from bionicmemory.services.chat_helper import ChatHelper

# 加载.env文件
load_dotenv()

# 使用统一日志配置
from bionicmemory.utils.logging_config import get_logger
logger = get_logger(__name__)

# 在文件顶部添加导入
from bionicmemory.services.local_embedding_service import get_embedding_service


class ChromaService:
    """
    ChromaDB向量数据库操作服务
    """

    @staticmethod
    def check_and_clear_database_on_startup() -> bool:
        """
        启动时检查并清除ChromaDB数据库
        如果存在.memory_cleared标记文件，则删除chroma_db目录

        Returns:
            bool: 是否执行了清除操作
        """
        import shutil

        try:
            # 标记文件路径
            marker_file = os.path.abspath("./memory/.memory_cleared")

            # 检查标记文件是否存在
            if not os.path.exists(marker_file):
                return False

            logger.info("检测到记忆清除标记文件，准备删除ChromaDB数据库...")

            # ChromaDB数据库路径
            chroma_db_path = os.path.abspath("./memory/chroma_db")

            # 删除chroma_db目录
            if os.path.exists(chroma_db_path):
                try:
                    shutil.rmtree(chroma_db_path)
                    logger.info(f"成功删除ChromaDB数据库目录: {chroma_db_path}")
                except Exception as e:
                    logger.error(f"删除ChromaDB数据库目录失败: {e}")
                    # 即使删除失败，也继续尝试删除标记文件
            else:
                logger.info(f"ChromaDB数据库目录不存在，跳过删除: {chroma_db_path}")

            # 删除标记文件
            try:
                os.remove(marker_file)
                logger.info(f"成功删除记忆清除标记文件: {marker_file}")
            except Exception as e:
                logger.error(f"删除标记文件失败: {e}")

            return True

        except Exception as e:
            logger.error(f"启动时清除数据库失败: {e}")
            return False

    def __init__(self, 
                 client_type: str = None,
                 path: Optional[str] = None,
                 host: str = None,
                 port: int = None,
                 chat_api_key: str = None,
                 chat_base_url: str = None):
        """
        初始化ChromaDB服务
        
        Args:
            client_type (str): 客户端类型，支持 'persistent', 'ephemeral', 'http'
            path (str): 持久化存储路径（仅persistent模式）
            host (str): 服务器地址（仅http模式）
            port (int): 服务器端口（仅http模式）
            chat_api_key (str): 聊天API密钥
            chat_base_url (str): 聊天API基础URL
        """
        try:
            # 从环境变量读取配置
            from dotenv import load_dotenv
            import os
            
            # 加载.env文件
            load_dotenv()
            
            # 设置默认值
            client_type = client_type or os.getenv('CHROMA_CLIENT_TYPE', 'persistent')
            path = path or os.getenv('CHROMA_PATH', './memory/chroma_db')
            path = os.path.abspath(path)  # 转换为绝对路径
            host = host or os.getenv('CHROMA_HOST', 'localhost')
            port = int(port or os.getenv('CHROMA_PORT', '8001'))
            chat_api_key = chat_api_key or os.getenv('OPENAI_API_KEY')
            chat_base_url = chat_base_url or os.getenv('OPENAI_API_BASE')
            
            # 初始化ChromaDB客户端
            if client_type == "persistent":
                self.client = chromadb.PersistentClient(path=path)
            elif client_type == "ephemeral":
                self.client = chromadb.EphemeralClient()
            elif client_type == "http":
                self.client = chromadb.HttpClient(host=host, port=port)
            else:
                raise ValueError(f"不支持的客户端类型: {client_type}")
            
            # 初始化聊天助手（如果需要）
            if chat_api_key and chat_base_url:
                self.chat_helper = ChatHelper(chat_api_key, chat_base_url)
                logger.info("聊天助手初始化完成")
            else:
                self.chat_helper = None
                logger.info("未配置聊天API，聊天功能不可用")
            
            # 初始化本地embedding服务
            self.local_embedding_service = get_embedding_service()
            logger.info("使用本地embedding服务")
            
            # 初始化自定义embedding函数相关变量
            self._custom_embedding_func = None
            self._embedding_function = None  # 本地模式不需要embedding函数
                
        except Exception as e:
            raise Exception(f"初始化ChromaDB客户端失败: {str(e)}")
    
    def create_collection(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        创建新的集合
        
        Args:
            name (str): 集合名称
            metadata (Dict[str, Any], optional): 集合元数据
            
        Returns:
            Collection: 集合对象
        """
        try:
            # 本地embedding模式，不使用ChromaDB的embedding函数
            embedding_function = None
            
            collection = self.client.create_collection(
                name=name,
                metadata=metadata,
                embedding_function=embedding_function
            )
            logger.info(f"成功创建集合: {name}")
            return collection
        except Exception as e:
            logger.error(f"创建集合失败: {name}, 错误: {e}")
            raise
    
    def get_or_create_collection(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        获取或创建集合
        
        Args:
            name (str): 集合名称
            metadata (Dict[str, Any], optional): 集合元数据
            
        Returns:
            Collection: 集合对象
        """
        try:
            embedding_function = None
            if self._custom_embedding_func is not None:
                self._embedding_function.custom_func = self._custom_embedding_func
                embedding_function = self._embedding_function
            
            collection = self.client.get_or_create_collection(
                name=name,
                metadata=metadata,
                embedding_function=embedding_function
            )
            logger.info(f"成功获取或创建集合: {name}")
            return collection
        except Exception as e:
            logger.error(f"获取或创建集合失败: {name}, 错误: {e}")
            raise
    
    def list_collections(self):
        """
        列出所有集合
        
        Returns:
            List[Collection]: 集合对象列表
        """
        try:
            collections = self.client.list_collections()
            logger.info(f"找到 {len(collections)} 个集合")
            return collections
        except Exception as e:
            logger.error(f"获取集合列表失败: {e}")
            raise
    
    def delete_collection(self, name: str):
        """
        删除集合
        
        Args:
            name (str): 集合名称
            
        Returns:
            None
        """
        try:
            self.client.delete_collection(name=name)
            logger.info(f"成功删除集合: {name}")
        except Exception as e:
            logger.error(f"删除集合失败: {name}, 错误: {e}")
            raise
    
    def add_documents(self, 
                     collection_name: str,
                     documents: List[str],
                     embeddings: List[List[float]] = None,
                     ids: Optional[List[str]] = None,
                     metadatas: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        向集合添加文档
        
        Args:
            collection_name (str): 集合名称
            documents (List[str]): 文档内容列表
            embeddings (List[List[float]], optional): 预计算的embedding向量列表
            ids (List[str], optional): 文档ID列表
            metadatas (List[Dict[str, Any]], optional): 文档元数据列表
            
        Returns:
            List[str]: 添加的文档ID列表
        """
        try:
            # 使用self.client确保集合存在
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._embedding_function
            )
            
            # 如果没有提供ID，自动生成
            if ids is None:
                ids = [f"doc_{i}" for i in range(len(documents))]
            
            # 如果提供了预计算的embedding，使用它们
            if embeddings is not None:
                # 验证参数长度一致性
                if len(documents) != len(embeddings):
                    raise ValueError(f"文档数量({len(documents)})与embedding数量({len(embeddings)})不匹配")
                
                collection.add(
                    documents=documents,
                    embeddings=embeddings,
                    ids=ids,
                    metadatas=metadatas
                )
            else:
                # 让ChromaDB自动生成embedding
                collection.add(
                    documents=documents,
                    ids=ids,
                    metadatas=metadatas
                )
            
            return ids  # ✅ 返回实际数据
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            raise  # ✅ 抛出异常
    
    def query_documents(self,
                       collection_name: str,
                       query_texts: List[str] = None,
                       query_embeddings: List[List[float]] = None,
                       n_results: int = 10,
                       where: Optional[Dict[str, Any]] = None,
                       include: Optional[List[str]] = None) -> Dict:
        """
        查询文档
        
        Args:
            collection_name (str): 集合名称
            query_texts (List[str], optional): 查询文本列表
            query_embeddings (List[List[float]], optional): 预计算的查询embedding列表
            n_results (int): 返回结果数量
            where (Dict[str, Any], optional): 元数据过滤条件
            include (List[str], optional): 需要返回的数据类型
            
        Returns:
            Dict: 查询结果字典
        """
        try:
            # 使用self.client确保集合存在
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._embedding_function
            )
            
            # 设置默认的include参数
            if include is None:
                include = ["documents", "metadatas", "distances", "embeddings"]
            
            # 优先使用预计算的embedding，避免重复计算
            if query_embeddings is not None:
                results = collection.query(
                    query_embeddings=query_embeddings,
                    n_results=n_results,
                    where=where,
                    include=include
                )
            else:
                results = collection.query(
                    query_texts=query_texts,
                    n_results=n_results,
                    where=where,
                    include=include
                )
            
            # 统一处理embeddings，确保返回list格式
            if 'embeddings' in results and results.get('embeddings') is not None:
                embeddings_data = results['embeddings']
                processed_embeddings = []
                for embedding_list in embeddings_data:
                    processed_embedding_list = []
                    for embedding in embedding_list:
                        if embedding is not None and hasattr(embedding, 'tolist'):
                            processed_embedding_list.append(embedding.tolist())
                        else:
                            processed_embedding_list.append(embedding)
                    processed_embeddings.append(processed_embedding_list)
                results['embeddings'] = processed_embeddings
            
            return results  # ✅ 返回实际数据
        except Exception as e:
            logger.error(f"查询文档失败: {e}")
            raise  # ✅ 抛出异常
    
    def get_documents(self,
                     collection_name: str,
                     ids: Optional[List[str]] = None,
                     limit: Optional[int] = None,
                     where: Optional[Dict[str, Any]] = None,
                     include: Optional[List[str]] = None) -> Dict:
        """
        获取文档
        
        Args:
            collection_name (str): 集合名称
            ids (List[str], optional): 文档ID列表
            limit (int, optional): 限制返回数量
            where (Dict[str, Any], optional): 元数据过滤条件
            include (List[str], optional): 需要返回的数据类型
            
        Returns:
            Dict: 文档结果字典
        """
        try:
            # 使用self.client确保集合存在
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._embedding_function
            )
            
            # 设置默认的include参数
            if include is None:
                include = ["documents", "metadatas"]
            
            results = collection.get(
                ids=ids,
                limit=limit,
                where=where,
                include=include
            )
            
            # 统一处理embeddings，确保返回list格式
            if 'embeddings' in results and results.get('embeddings') is not None:
                embeddings_data = results['embeddings']
                processed_embeddings = []
                for embedding_list in embeddings_data:
                    processed_embedding_list = []
                    for embedding in embedding_list:
                        if embedding is not None and hasattr(embedding, 'tolist'):
                            processed_embedding_list.append(embedding.tolist())
                        else:
                            processed_embedding_list.append(embedding)
                    processed_embeddings.append(processed_embedding_list)
                results['embeddings'] = processed_embeddings
            
            return results  # ✅ 返回实际数据
        except Exception as e:
            logger.error(f"获取文档失败: {e}")
            raise  # ✅ 抛出异常
    
    def update_documents(self,
                        collection_name: str,
                        ids: List[str],
                        documents: Optional[List[str]] = None,
                        metadatas: Optional[List[Dict[str, Any]]] = None) -> Dict:
        """
        更新文档
        
        Args:
            collection_name (str): 集合名称
            ids (List[str]): 文档ID列表
            documents (List[str], optional): 新的文档内容
            metadatas (List[Dict[str, Any]], optional): 新的元数据
            
        Returns:
            Dict: 更新后的文档数据
        """
        try:
            # 使用self.client确保集合存在
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._embedding_function
            )
            
            collection.update(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            # 返回更新后的文档数据
            return collection.get(ids=ids)  # ✅ 返回实际数据
        except Exception as e:
            logger.error(f"更新文档失败: {e}")
            raise  # ✅ 抛出异常
    
    def delete_documents(self,
                        collection_name: str,
                        ids: Optional[List[str]] = None,
                        where: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        删除文档
        
        Args:
            collection_name (str): 集合名称
            ids (List[str], optional): 文档ID列表
            where (Dict[str, Any], optional): 元数据过滤条件
            
        Returns:
            List[str]: 删除的文档ID列表
        """
        try:
            # 使用self.client确保集合存在
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._embedding_function
            )
            
            # 如果提供了ids，直接删除
            if ids:
                collection.delete(ids=ids)
                return ids  # ✅ 返回实际数据
            else:
                # 如果使用where条件，先查询要删除的文档
                if where:
                    results = collection.get(where=where)
                    deleted_ids = results.get('ids', [])
                    if deleted_ids:
                        collection.delete(ids=deleted_ids)
                    return deleted_ids  # ✅ 返回实际数据
                else:
                    # 删除所有文档
                    all_results = collection.get()
                    all_ids = all_results.get('ids', [])
                    if all_ids:
                        collection.delete(ids=all_ids)
                    return all_ids  # ✅ 返回实际数据
                    
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            raise  # ✅ 抛出异常
    
    def count_documents(self, collection_name: str) -> int:
        """
        统计集合中的文档数量
        
        Args:
            collection_name (str): 集合名称
            
        Returns:
            int: 文档数量
        """
        try:
            # 使用self.client确保集合存在
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._embedding_function
            )
            count = collection.count()
            return count  # ✅ 返回实际数据
        except Exception as e:
            logger.error(f"统计文档数量失败: {e}")
            raise  # ✅ 抛出异常
    
    def peek_documents(self, collection_name: str, limit: int = 10) -> Dict:
        """
        预览集合中的文档
        
        Args:
            collection_name (str): 集合名称
            limit (int): 预览数量限制
            
        Returns:
            Dict: 预览结果数据
        """
        try:
            # 使用self.client确保集合存在
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._embedding_function
            )
            results = collection.peek(limit=limit)
            return results  # ✅ 返回实际数据
        except Exception as e:
            logger.error(f"预览文档失败: {e}")
            raise  # ✅ 抛出异常
    
    def custom_embedding(self, texts: List[str]) -> List[List[float]]:
        """
        自定义嵌入函数（预留接口）
        
        Args:
            texts (List[str]): 待嵌入的文本列表
            
        Returns:
            List[List[float]]: 嵌入向量列表
        """
        # 函数体为pass，后续手动实现
        pass
    
    def set_custom_embedding_function(self, embedding_func: Callable[[List[str]], List[List[float]]]) -> None:
        """
        设置自定义嵌入函数
        
        Args:
            embedding_func: 自定义嵌入函数，接受文本列表，返回向量列表
            
        Returns:
            None
        """
        try:
            self._custom_embedding_func = embedding_func
            # ✅ 不返回值，成功就成功
        except Exception as e:
            logger.error(f"设置自定义嵌入函数失败: {e}")
            raise  # ✅ 抛出异常
    
    def get_custom_embedding_function(self) -> Optional[Callable]:
        """
        获取当前设置的自定义嵌入函数
        
        Returns:
            Optional[Callable]: 当前的自定义嵌入函数，如果未设置则返回None
        """
        return self._custom_embedding_func
    
    def create_embeddings(self, texts: List[str], model: str = None) -> List[List[float]]:
        """
        使用本地服务生成文本的embedding向量
        """
        # 使用本地embedding服务
        embeddings = self.local_embedding_service.encode_texts(texts)
        return embeddings.tolist()
    
    def get_embedding_dimension(self) -> int:
        """
        获取embedding维度（从embedding服务动态获取）
        """
        # 从 embedding 服务获取实际维度
        model_info = self.local_embedding_service.get_model_info()
        return model_info.get('embedding_dim', 1024)

    def get_collection(self, name: str):
        """
        获取集合对象
        
        Args:
            name (str): 集合名称
            
        Returns:
            Collection: 集合对象
        """
        try:
            collection = self.client.get_collection(name)
            logger.info(f"成功获取集合: {name}")
            return collection
        except Exception as e:
            logger.error(f"获取集合失败: {name}, 错误: {e}")
            raise
