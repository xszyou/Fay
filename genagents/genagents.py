import uuid

from genagents.modules.interaction import *
from genagents.modules.memory_stream import *


# ############################################################################
# ###                        GENERATIVE AGENT CLASS                        ###
# ############################################################################

class GenerativeAgent: 
  def __init__(self, agent_folder=None):
    if agent_folder: 
      # We stop the process if the agent storage folder already exists. 
      if not check_if_file_exists(f"{agent_folder}/scratch.json"):
        print ("Generative agent does not exist in the current location.")
        return 
      
      # Loading the agent's memories. 
      try:
        with open(f"{agent_folder}/scratch.json", 'r', encoding='utf-8') as json_file:
          scratch = json.load(json_file)
        with open(f"{agent_folder}/memory_stream/embeddings.json", 'r', encoding='utf-8') as json_file:
          embeddings = json.load(json_file)
        with open(f"{agent_folder}/memory_stream/nodes.json", 'r', encoding='utf-8') as json_file:
          nodes = json.load(json_file)
      except Exception as e:
        print(f"加载代理记忆时出错: {str(e)}")
        # 如果加载失败，创建空的记忆
        scratch = {}
        embeddings = {}
        nodes = []

      self.id = uuid.uuid4()
      self.scratch = scratch
      self.memory_stream = MemoryStream(nodes, embeddings)

    else: 
      self.id = uuid.uuid4()
      self.scratch = {}
      self.memory_stream = MemoryStream([], {})


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
    Given a save_code, save the agents' state in the storage. Right now, the 
    save directory works as follows: 
    'storage/<agent_name>/<save_code>'

    As you grow different versions of the agent, save the new agent state in 
    a different save code location. Remember that 'init' is the originally
    initialized agent directory.

    Parameters:
      save_code: str
    Returns: 
      None
    """
    try:
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

      # Saving the agent's scratch memories. 
      with open(f"{storage}/scratch.json", "w", encoding='utf-8') as json_file:
        json.dump(self.scratch, json_file, ensure_ascii=False, indent=2)

      # Saving the agent's meta information. 
      with open(f"{storage}/meta.json", "w", encoding='utf-8') as json_file:
        json.dump(self.package(), json_file, ensure_ascii=False, indent=2)
    except Exception as e:
      print(f"保存代理记忆时出错: {str(e)}")


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
    self.memory_stream.reflect(anchor, time_step)


  def categorical_resp(self, questions): 
    ret = categorical_resp(self, questions)
    return ret
    

  def numerical_resp(self, questions, float_resp=False): 
    ret = numerical_resp(self, questions, float_resp)
    return ret


  def utterance(self, curr_dialogue, context=""): 
    ret = utterance(self, curr_dialogue, context)
    return ret 
