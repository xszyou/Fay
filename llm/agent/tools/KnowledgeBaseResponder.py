import os
from typing import Any

from langchain.tools import BaseTool
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain.indexes.vectorstore import VectorstoreIndexCreator, VectorStoreIndexWrapper
from langchain_community.vectorstores.chroma import Chroma
from langchain_openai import ChatOpenAI
import hashlib
#若要使用请自行配置
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENAI_API_BASE"] = "https://api.openai.com/v1"
index_name = "knowledge_data"
folder_path = "agent/tools/KnowledgeBaseResponder/knowledge_base"  
local_persist_path = "agent/tools/KnowledgeBaseResponder"
md5_file_path = os.path.join(local_persist_path, "pdf_md5.txt")
#
class KnowledgeBaseResponder(BaseTool):
    name = "KnowledgeBaseResponder"
    description = """此工具用于连接本地知识库获取问题答案，使用时请传入相关问题作为参数，例如：“草梅最适合的生长温度”"""

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        self.save_all()
        result = self.question(para)
        return result

    def generate_file_md5(self, file_path):
        hasher = hashlib.md5()
        with open(file_path, 'rb') as afile:
            buf = afile.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def load_md5_list(self):
        if os.path.exists(md5_file_path):
            with open(md5_file_path, 'r') as file:
                return {line.split(",")[0]: line.split(",")[1].strip() for line in file}
        return {}

    def update_md5_list(self, file_name, md5_value):
        md5_list = self.load_md5_list()
        md5_list[file_name] = md5_value
        with open(md5_file_path, 'w') as file:
            for name, md5 in md5_list.items():
                file.write(f"{name},{md5}\n")

    def load_all_pdfs(self, folder_path):
        md5_list = self.load_md5_list()
        for file_name in os.listdir(folder_path):
            if file_name.endswith(".pdf"):
                file_path = os.path.join(folder_path, file_name)
                file_md5 = self.generate_file_md5(file_path)
                if file_name not in md5_list or md5_list[file_name] != file_md5:
                    print(f"正在加载 {file_name} 到索引...")
                    self.load_pdf_and_save_to_index(file_path, index_name)
                    self.update_md5_list(file_name, file_md5)

    def get_index_path(self, index_name):
        return os.path.join(local_persist_path, index_name)

    def load_pdf_and_save_to_index(self, file_path, index_name):
        loader = PyPDFLoader(file_path)
        embedding = OpenAIEmbeddings(model="text-embedding-ada-002")
        index = VectorstoreIndexCreator(embedding=embedding, vectorstore_kwargs={"persist_directory": self.get_index_path(index_name)}).from_loaders([loader])
        index.vectorstore.persist()

    def load_index(self, index_name):
        index_path = self.get_index_path(index_name)
        embedding = OpenAIEmbeddings(model="text-embedding-ada-002")
        vectordb = Chroma(persist_directory=index_path, embedding_function=embedding)
        return VectorStoreIndexWrapper(vectorstore=vectordb)

    def save_all(self):
        self.load_all_pdfs(folder_path)

    def question(self, cont):
        try:
            info = cont
            index = self.load_index(index_name)    
            llm = ChatOpenAI(model="gpt-4-0125-preview")
            ans = index.query(info, llm, chain_type="map_reduce")
            return ans
        except Exception as e:
            print(f"请求失败: {e}")
            return "抱歉，我现在太忙了，休息一会，请稍后再试。"


if __name__ == "__main__":
    tool = KnowledgeBaseResponder()
    info = tool.run("草莓最适合的生长温度")
    print(info)
