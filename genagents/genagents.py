import uuid
import json
import os
import sys
from datetime import datetime

# 添加项目根目录到系统路径，以便导入utils模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import config_util as cfg
from utils import util

from genagents.modules.interaction import *
from genagents.modules.memory_stream import *


# ############################################################################
# ###                        GENERATIVE AGENT CLASS                        ###
# ############################################################################

class GenerativeAgent: 
  def __init__(self, agent_folder=None):
    if agent_folder: 
      # 检查记忆目录是否存在
      memory_stream_exists = check_if_file_exists(f"{agent_folder}/memory_stream/nodes.json") and check_if_file_exists(f"{agent_folder}/memory_stream/embeddings.json")
      
      # 加载记忆流数据
      try:
        if memory_stream_exists:
          with open(f"{agent_folder}/memory_stream/embeddings.json", 'r', encoding='utf-8') as json_file:
            embeddings = json.load(json_file)
          with open(f"{agent_folder}/memory_stream/nodes.json", 'r', encoding='utf-8') as json_file:
            nodes = json.load(json_file)
        else:
          embeddings = {}
          nodes = []
      except Exception as e:
        util.log(1, f"加载代理记忆时出错: {str(e)}")
        # 如果加载失败，创建空的记忆
        embeddings = {}
        nodes = []

      self.id = uuid.uuid4()
      # 从配置文件实时加载数字人属性
      self.scratch = self._load_scratch_from_config()
      self.memory_stream = MemoryStream(nodes, embeddings)

    else: 
      self.id = uuid.uuid4()
      # 从配置文件实时加载数字人属性
      self.scratch = self._load_scratch_from_config()
      self.memory_stream = MemoryStream([], {})

  def _load_scratch_from_config(self):
    """
    从配置文件实时加载数字人属性
    
    返回:
        dict: 包含数字人属性的字典
    """
    try:
      # 确保配置已加载
      if not hasattr(cfg, 'config') or cfg.config is None:
        cfg.load_config()
      
      # 从配置文件加载数字人属性
      scratch_data = {
          "first_name": cfg.config["attribute"]["name"],
          "last_name": "",
          "age": cfg.config["attribute"]["age"],
          "sex": cfg.config["attribute"]["gender"],
          "additional": cfg.config["attribute"]["additional"],
          "birthplace": cfg.config["attribute"]["birth"],
          "position": cfg.config["attribute"]["position"],
          "zodiac": cfg.config["attribute"]["zodiac"],
          "constellation": cfg.config["attribute"]["constellation"],
          "contact": cfg.config["attribute"]["contact"],
          "voice": cfg.config["attribute"]["voice"],  
          "goal": cfg.config["attribute"]["goal"],
          "occupation": cfg.config["attribute"]["job"],
          "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      }
      return scratch_data
    except Exception as e:
      util.log(1, f"从配置加载数字人属性时出错: {str(e)}")
      # 返回空字典作为默认值
      return {}

  def update_scratch(self, update): 
    self.scratch.update(update)
      

  def package(self): 
    """
    Packaging the agent's meta info for saving. 

    Parameters:
      None
    Returns: 
      packaged dictionary
    """
    return {"id": str(self.id)}


  def save(self, save_directory): 
    """
    Given a save_directory, save the agents' state in the storage.
    
    Parameters:
      save_directory: str - 保存目录的路径
    Returns: 
      None
    """
    try:
      # 保存前先更新scratch数据
      self.scratch = self._load_scratch_from_config()
      
      # Name of the agent and the current save location. 
      storage = save_directory
      create_folder_if_not_there(f"{storage}/memory_stream")
      
      # 确保embeddings不为None
      if self.memory_stream.embeddings is None:
          self.memory_stream.embeddings = {}
      
      # Saving the agent's memory stream. This includes saving the embeddings 
      # as well as the nodes. 
      with open(f"{storage}/memory_stream/embeddings.json", "w", encoding='utf-8') as json_file:
        json.dump(self.memory_stream.embeddings, 
                  json_file, ensure_ascii=False, indent=2)
      with open(f"{storage}/memory_stream/nodes.json", "w", encoding='utf-8') as json_file:
        json.dump([node.package() for node in self.memory_stream.seq_nodes], 
                  json_file, ensure_ascii=False, indent=2)

      # Saving the agent's meta information. 
      with open(f"{storage}/meta.json", "w", encoding='utf-8') as json_file:
        json.dump(self.package(), json_file, ensure_ascii=False, indent=2)
      
      util.log(1, f"已保存代理记忆")
    except Exception as e:
      util.log(1, f"保存代理记忆时出错: {str(e)}")


  def get_fullname(self): 
    if "first_name" in self.scratch and "last_name" in self.scratch:
      return f"{self.scratch['first_name']} {self.scratch['last_name']}"
    else: 
      return ""

  def get_self_description(self): 
    return str(self.scratch)

  def remember(self, content, time_step=0): 
    """
    Add a new observation to the memory stream. 

    Parameters:
      content: The content of the current memory record that we are adding to
        the agent's memory stream. 
    Returns: 
      None
    """
    self.memory_stream.remember(content, time_step)


  def reflect(self, anchor, time_step=0): 
    """
    Add a new reflection to the memory stream. 

    Parameters:
      anchor: str reflection anchor
    Returns: 
      None
    """
    self.memory_stream.reflect(anchor, time_step=time_step)


  def categorical_resp(self, questions): 
    ret = categorical_resp(self, questions)
    return ret
    

  def numerical_resp(self, questions, float_resp=False): 
    ret = numerical_resp(self, questions, float_resp)
    return ret


  def utterance(self, curr_dialogue, context=""): 
    ret = utterance(self, curr_dialogue, context)
    return ret 
