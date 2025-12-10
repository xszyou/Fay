import openai
import time
import base64
from typing import List, Dict, Any, Union, Optional
import os
from simulation_engine.settings import *
from utils import config_util as cfg


# 确保配置已加载
cfg.load_config()

# 初始化 OpenAI 客户端
client = openai.OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_API_BASE
)

# 设置全局API密钥（兼容性考虑）
openai.api_key = OPENAI_API_KEY

# 如果环境变量中没有设置，则设置环境变量（某些库可能依赖环境变量）
if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
if "OPENAI_API_BASE" not in os.environ and OPENAI_API_BASE:
    os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE


# ============================================================================
# #######################[SECTION 1: HELPER FUNCTIONS] #######################
# ============================================================================

def print_run_prompts(prompt_input: Union[str, List[str]], 
                      prompt: str, 
                      output: str) -> None:
  print (f"=== START =======================================================")
  print ("~~~ prompt_input    ----------------------------------------------")
  print (prompt_input, "\n")
  print ("~~~ prompt    ----------------------------------------------------")
  print (prompt, "\n")
  print ("~~~ output    ----------------------------------------------------")
  print (output, "\n") 
  print ("=== END ==========================================================")
  print ("\n\n\n")


def generate_prompt(prompt_input: Union[str, List[str]], 
                    prompt_lib_file: str) -> str:
  """
  通过用输入替换模板文件中的占位符来生成提示
  
  参数:
    prompt_input: 输入文本，可以是字符串或字符串列表
    prompt_lib_file: 模板文件路径
    
  返回:
    生成的提示文本
  """
  # 确保prompt_input是列表类型
  if isinstance(prompt_input, str):
    prompt_input = [prompt_input]
  
  # 确保所有输入都是字符串类型
  prompt_input = [str(i) for i in prompt_input]

  try:
    # 使用UTF-8编码读取模板文件
    with open(prompt_lib_file, "r", encoding='utf-8') as f:
      prompt = f.read()
  except FileNotFoundError:
    print(f"生成提示错误: 未找到模板文件 {prompt_lib_file}")
    return "ERROR: 模板文件不存在"
  except Exception as e:
    print(f"读取模板文件时出错: {str(e)}")
    return f"ERROR: 读取模板文件时出错 - {str(e)}"

  # 替换占位符
  for count, input_text in enumerate(prompt_input):
    prompt = prompt.replace(f"!<INPUT {count}>!", input_text)

  # 处理注释块
  if "<commentblockmarker>###</commentblockmarker>" in prompt:
    prompt = prompt.split("<commentblockmarker>###</commentblockmarker>")[1]

  return prompt.strip()


# ============================================================================
# ####################### [SECTION 2: SAFE GENERATE] #########################
# ============================================================================

def gpt_request(prompt: str, 
                model: str = "gpt-4o", 
                max_tokens: int = 1500) -> str:
  """
  向OpenAI的GPT模型发送请求
  
  参数:
    prompt: 提示文本
    model: 模型名称，默认为"gpt-4o"
    max_tokens: 最大生成令牌数，默认为1500
    
  返回:
    模型生成的响应文本
  """
  # 确保prompt是字符串类型
  if not isinstance(prompt, str):
    print("GPT请求错误: 提示文本必须是字符串类型")
    return "GENERATION ERROR: 提示文本必须是字符串类型"
  
  # 处理o1-preview模型
  if model == "o1-preview": 
    try:
      response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
      )
      # 确保返回的内容是UTF-8编码
      return response.choices[0].message.content
    except Exception as e:
      error_msg = f"GENERATION ERROR: {str(e)}"
      print(error_msg)
      return error_msg

  # 处理其他模型
  try:
    response = client.chat.completions.create(
      model=model,
      messages=[{"role": "user", "content": prompt}],
      max_tokens=max_tokens,
      temperature=0.7
    )
    # 确保返回的内容是UTF-8编码
    return response.choices[0].message.content
  except Exception as e:
    error_msg = f"GENERATION ERROR: {str(e)}"
    print(error_msg)
    return error_msg


def gpt4_vision(messages: List[dict], max_tokens: int = 1500) -> str:
  """Make a request to OpenAI's GPT-4 Vision model."""
  try:
    client = openai.OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE
    )
    response = client.chat.completions.create(
      model="gpt-4o",
      messages=messages,
      max_tokens=max_tokens,
      temperature=0.7
    )
    return response.choices[0].message.content
  except Exception as e:
    return f"GENERATION ERROR: {str(e)}"


def chat_safe_generate(prompt_input: Union[str, List[str]], 
                       prompt_lib_file: str,
                       gpt_version: str = "gpt-4o", 
                       repeat: int = 1,
                       fail_safe: str = "error", 
                       func_clean_up: callable = None,
                       verbose: bool = False,
                       max_tokens: int = 1500,
                       file_attachment: str = None,
                       file_type: str = None) -> tuple:
  """Generate a response using GPT models with error handling & retries."""
  if file_attachment and file_type:
    prompt = generate_prompt(prompt_input, prompt_lib_file)
    messages = [{"role": "user", "content": prompt}]

    if file_type.lower() == 'image':
      with open(file_attachment, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
      messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": "Please refer to the attached image."},
            {"type": "image_url", "image_url": 
              {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]
      })
      response = gpt4_vision(messages, max_tokens)

    elif file_type.lower() == 'pdf':
      pdf_text = extract_text_from_pdf_file(file_attachment)
      pdf = f"PDF attachment in text-form:\n{pdf_text}\n\n"
      instruction = generate_prompt(prompt_input, prompt_lib_file)
      prompt = f"{pdf}"
      prompt += f"<End of the PDF attachment>\n=\nTask description:\n{instruction}"
      response = gpt_request(prompt, gpt_version, max_tokens)

  else:
    prompt = generate_prompt(prompt_input, prompt_lib_file)
    for i in range(repeat):
      response = gpt_request(prompt, model=gpt_version)
      if response != "GENERATION ERROR":
        break
      time.sleep(2**i)
    else:
      response = fail_safe

  if func_clean_up:
    response = func_clean_up(response, prompt=prompt)


  if verbose or DEBUG:
    print_run_prompts(prompt_input, prompt, response)

  return response, prompt, prompt_input, fail_safe

# ============================================================================
# #################### [SECTION 3: OTHER API FUNCTIONS] ######################
# ============================================================================


# 添加模拟 embedding 函数（仅作为兜底）
def _create_mock_embedding(dimension=1536):
  """创建一个可重复的模拟 embedding 向量，用于离线兜底。"""
  import random
  import math
  import hashlib
  
  def _get_mock_vector(text):
    """为给定文本生成可重复的伪 embedding。"""
    try:
      if isinstance(text, str):
        text_bytes = text.encode('utf-8')
      else:
        text_bytes = str(text).encode('utf-8')
      hash_value = int(hashlib.sha256(text_bytes).hexdigest(), 16) % (10 ** 8)
      random.seed(hash_value)
    except Exception as e:
      print(f"处理文本哈希时出错，使用固定种子: {str(e)}")
      random.seed(42)
    vector = [random.uniform(-1, 1) for _ in range(dimension)]
    magnitude = math.sqrt(sum(x * x for x in vector))
    normalized_vector = [x / magnitude for x in vector]
    return normalized_vector
  
  return _get_mock_vector

# 创建模拟函数实例和 API 服务占位
_mock_embedding_function = _create_mock_embedding(1536)
_api_embedding_service = None

def get_text_embedding(text: str, 
                       model: str = "text-embedding-3-small") -> List[float]:
  """
  生成文本的 embedding。优先调用 system.conf 配置的 API 服务；
  若 API 调用失败，则回退到本地模拟 embedding，保证流程不断。
  """
  try:
    if not isinstance(text, str):
      print("Embedding 错误: 输入必须是字符串")
      return [0.0] * 1536
    if not text.strip():
      print("Embedding 警告: 输入字符串为空")
      return [0.0] * 1536

    text = text.replace("\n", " ").strip()

    # 优先使用外部 API embedding 服务
    try:
      from bionicmemory.services.api_embedding_service import get_embedding_service
      service = get_embedding_service()
      return service.encode_text(text)
    except Exception as api_err:
      # API 调用失败时使用本地模拟
      print(f"调用 API embedding 失败，使用模拟向量代替: {api_err}")
      return _mock_embedding_function(text)
  except Exception as e:
    print(f"生成 embedding 时出错: {str(e)}")
    return [0.0] * 1536
