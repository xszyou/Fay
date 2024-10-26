import hashlib
import os
from pgpt_python.client import PrivateGPTApi

client = PrivateGPTApi(base_url="http://127.0.0.1:8001")

index_name = "knowledge_data"
folder_path = "llm/privategpt/knowledge_base"
local_persist_path = "llm/privategpt"
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
                print(f"正在上传 {file_name} 到服务器...")
                with open(file_path, "rb") as f:
                    try:
                        ingested_file_doc_id = client.ingestion.ingest_file(file=f).data[0].doc_id
                        print(f"Ingested file doc id: {ingested_file_doc_id}")
                        update_md5_list(file_name, file_md5)
                    except Exception as e:
                        print(f"上传 {file_name} 失败: {e}")


def question(cont, uid=0):
    load_all_pdfs(folder_path)
    text = client.contextual_completions.prompt_completion(
        prompt=cont
    ).choices[0].message.content
    return text


def save_all():
    load_all_pdfs(folder_path)

if __name__ == "__main__":
    print(question("土豆怎么做"))
