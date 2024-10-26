import hashlib
import os

from langchain.document_loaders import PyPDFLoader
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.indexes.vectorstore import VectorstoreIndexCreator, VectorStoreIndexWrapper
from langchain.vectorstores.chroma import Chroma
from langchain.chat_models import ChatOpenAI

from utils import config_util as cfg
from utils import util

index_name = "knowledge_data"
folder_path = "llm/langchain/knowledge_base"  
local_persist_path = "llm/langchain"
md5_file_path = os.path.join(local_persist_path, "pdf_md5.txt")

def generate_file_md5(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as afile:
        buf = afile.read()
        hasher.update(buf)
    return hasher.hexdigest()

def load_md5_list():
    if os.path.exists(md5_file_path):
        with open(md5_file_path, 'r') as file:
            return {line.split(",")[0]: line.split(",")[1].strip() for line in file}
    return {}

def update_md5_list(file_name, md5_value):
    md5_list = load_md5_list()
    md5_list[file_name] = md5_value
    with open(md5_file_path, 'w') as file:
        for name, md5 in md5_list.items():
            file.write(f"{name},{md5}\n")

def load_all_pdfs(folder_path):
    md5_list = load_md5_list()
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".pdf"):
            file_path = os.path.join(folder_path, file_name)
            file_md5 = generate_file_md5(file_path)
            if file_name not in md5_list or md5_list[file_name] != file_md5:
                util.log(1, f"正在加载 {file_name} 到索引...")
                load_pdf_and_save_to_index(file_path, index_name)
                update_md5_list(file_name, file_md5)

def get_index_path(index_name):
    return os.path.join(local_persist_path, index_name)

def load_pdf_and_save_to_index(file_path, index_name):
    try:
        loader = PyPDFLoader(file_path)
        embedding = OpenAIEmbeddings(model="text-embedding-ada-002")
        index = VectorstoreIndexCreator(embedding=embedding, vectorstore_kwargs={"persist_directory": get_index_path(index_name)}).from_loaders([loader])
        index.vectorstore.persist()
    except Exception as e:
        util.log(1, f"加载 {file_path} 失败...")
        print(e)

def load_index(index_name):
    index_path = get_index_path(index_name)
    embedding = OpenAIEmbeddings(model="text-embedding-ada-002")
    vectordb = Chroma(persist_directory=index_path, embedding_function=embedding)
    return VectorStoreIndexWrapper(vectorstore=vectordb)

def save_all():
    os.environ['OPENAI_API_KEY'] = cfg.key_gpt_api_key
    os.environ['OPENAI_API_BASE'] = cfg.gpt_base_url
    if cfg.proxy_config != None:
            os.environ["OPENAI_PROXY"] = cfg.proxy_config
    load_all_pdfs(folder_path)


def generate_prompt(question):
    context = "你是数字人Fay。你的知识不仅来源于所给到的文本知识，还包括经过深度学习的广泛数据集。"
    instruction = "在回答问题时，展现你的智能就像是从你的全面知识库中提取答案，而非依赖于所给到的文本知识来源。"
    creative_instruction = "不要在回答中表明'根据所提供的文本信息'，你需要表现得如同这些答案是你独立思考的结果。"
    complexity_handling = "当面对复杂问题时，以一种理解深刻且透彻的方式回答，确保答案的深度和广度。"
    info = f"{context}\n{instruction}\n{creative_instruction}\n{complexity_handling}\n问题：{question}\n回答："
    return info

def question(cont, uid=0):
    try:
        save_all()
        info = generate_prompt(cont)
        index = load_index(index_name)    
        llm = ChatOpenAI(model="gpt-3.5-turbo-16k")
        ans = index.query(info, llm, chain_type="map_reduce")
        return ans
    except Exception as e:
        util.log(1, f"请求失败: {e}")
        return "抱歉，我现在太忙了，休息一会，请稍后再试。"
    


