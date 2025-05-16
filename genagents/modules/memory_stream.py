import math
import sys
import datetime
import random
import string
import re

from numpy import dot
from numpy.linalg import norm

from simulation_engine.settings import * 
from simulation_engine.global_methods import *
from simulation_engine.gpt_structure import *
from simulation_engine.llm_json_parser import *


def run_gpt_generate_importance(
  records, 
  prompt_version="1",
  gpt_version="GPT4o",  
  verbose=False):

  def create_prompt_input(records):
    records_str = ""
    for count, r in enumerate(records): 
      records_str += f"Item {str(count+1)}:\n"
      records_str += f"{r}\n"
    return [records_str]

  def _func_clean_up(gpt_response, prompt=""): 
    gpt_response = extract_first_json_dict(gpt_response)
    # 处理gpt_response为None的情况
    if gpt_response is None:
      print("警告: extract_first_json_dict返回None，使用默认值")
      return [50]  # 返回默认重要性分数
    return list(gpt_response.values())

  def _get_fail_safe():
    return 25

  if len(records) > 1: 
    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/memory_stream/importance_score/batch_v1.txt" 
  else: 
    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/memory_stream/importance_score/singular_v1.txt" 

  prompt_input = create_prompt_input(records) 
  fail_safe = _get_fail_safe() 

  output, prompt, prompt_input, fail_safe = chat_safe_generate(
    prompt_input, prompt_lib_file, gpt_version, 1, fail_safe, 
    _func_clean_up, verbose)

  return output, [output, prompt, prompt_input, fail_safe]


def generate_importance_score(records): 
  return run_gpt_generate_importance(records, "1", LLM_VERS)[0]


def run_gpt_generate_reflection(
  records, 
  anchor, 
  reflection_count,
  prompt_version="1",
  gpt_version="GPT4o",  
  verbose=False):

  def create_prompt_input(records, anchor, reflection_count):
    records_str = ""
    for count, r in enumerate(records): 
      records_str += f"Item {str(count+1)}:\n"
      records_str += f"{r}\n"
    return [records_str, reflection_count, anchor]

  def _func_clean_up(gpt_response, prompt=""): 
    return extract_first_json_dict(gpt_response)["reflection"]

  def _get_fail_safe():
    return []

  if reflection_count > 1: 
    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/memory_stream/reflection/batch_v1.txt" 
  else: 
    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/memory_stream/reflection/singular_v1.txt" 

  prompt_input = create_prompt_input(records, anchor, reflection_count) 
  fail_safe = _get_fail_safe() 

  output, prompt, prompt_input, fail_safe = chat_safe_generate(
    prompt_input, prompt_lib_file, gpt_version, 1, fail_safe, 
    _func_clean_up, verbose)

  return output, [output, prompt, prompt_input, fail_safe]


def generate_reflection(records, anchor, reflection_count): 
  records = [i.content for i in records]
  return run_gpt_generate_reflection(records, anchor, reflection_count, "1", 
                                     LLM_VERS)[0]


# ##############################################################################
# ###                 HELPER FUNCTIONS FOR GENERATIVE AGENTS                 ###
# ##############################################################################

def get_random_str(length):
  """
  Generates a random string of alphanumeric characters with the specified 
  length. This function creates a random string by selecting characters from 
  the set of uppercase letters, lowercase letters, and digits. The length of 
  the random string is determined by the 'length' parameter.

  Parameters: 
    length (int): The desired length of the random string.
  Returns: 
    random_string: A randomly generated string of the specified length.
  
  Example:
    >>> get_random_str(8)
        'aB3R7tQ2'
  """
  characters = string.ascii_letters + string.digits
  random_string = ''.join(random.choice(characters) for _ in range(length))
  return random_string


def cos_sim(a, b): 
  """
  This function calculates the cosine similarity between two input vectors 
  'a' and 'b'. Cosine similarity is a measure of similarity between two 
  non-zero vectors of an inner product space that measures the cosine 
  of the angle between them.

  Parameters: 
    a: 1-D array object 
    b: 1-D array object 
  Returns: 
    A scalar value representing the cosine similarity between the input 
    vectors 'a' and 'b'.
  
  Example: 
    >>> a = [0.3, 0.2, 0.5]
    >>> b = [0.2, 0.2, 0.5]
    >>> cos_sim(a, b)
  """
  return dot(a, b)/(norm(a)*norm(b))


def normalize_dict_floats(d, target_min, target_max):
  """
  This function normalizes the float values of a given dictionary 'd' between 
  a target minimum and maximum value. The normalization is done by scaling the
  values to the target range while maintaining the same relative proportions 
  between the original values.

  Parameters: 
    d: Dictionary. The input dictionary whose float values need to be 
       normalized.
    target_min: Integer or float. The minimum value to which the original 
                values should be scaled.
    target_max: Integer or float. The maximum value to which the original 
                values should be scaled.
  Returns: 
    d: A new dictionary with the same keys as the input but with the float
       values normalized between the target_min and target_max.

  Example: 
    >>> d = {'a':1.2,'b':3.4,'c':5.6,'d':7.8}
    >>> target_min = -5
    >>> target_max = 5
    >>> normalize_dict_floats(d, target_min, target_max)
  """
  # 检查字典是否为None或为空
  if d is None:
    print("警告: normalize_dict_floats接收到None字典")
    return {}
  
  if not d:
    print("警告: normalize_dict_floats接收到空字典")
    return {}
  
  try:
    min_val = min(val for val in d.values())
    max_val = max(val for val in d.values())
    range_val = max_val - min_val
  
    if range_val == 0: 
      for key, val in d.items(): 
        d[key] = (target_max - target_min)/2
    else: 
      for key, val in d.items():
        d[key] = ((val - min_val) * (target_max - target_min) 
                  / range_val + target_min)
    return d
  except Exception as e:
    print(f"normalize_dict_floats处理字典时出错: {str(e)}")
    # 返回原始字典，避免处理失败
    return d


def top_highest_x_values(d, x):
  """
  This function takes a dictionary 'd' and an integer 'x' as input, and 
  returns a new dictionary containing the top 'x' key-value pairs from the 
  input dictionary 'd' with the highest values.

  Parameters: 
    d: Dictionary. The input dictionary from which the top 'x' key-value pairs 
       with the highest values are to be extracted.
    x: Integer. The number of top key-value pairs with the highest values to
       be extracted from the input dictionary.
  Returns: 
    A new dictionary containing the top 'x' key-value pairs from the input 
    dictionary 'd' with the highest values.
  
  Example: 
    >>> d = {'a':1.2,'b':3.4,'c':5.6,'d':7.8}
    >>> x = 3
    >>> top_highest_x_values(d, x)
  """
  top_v = dict(sorted(d.items(), 
                      key=lambda item: item[1], 
                      reverse=True)[:x])
  return top_v


def extract_recency(seq_nodes):
  """
  Gets the current Persona object and a list of nodes that are in a 
  chronological order, and outputs a dictionary that has the recency score
  calculated.

  Parameters: 
    nodes: A list of Node object in a chronological order. 
  Returns: 
    recency_out: A dictionary whose keys are the node.node_id and whose values
                 are the float that represents the recency score. 
  """
  # 检查seq_nodes是否为None或为空
  if seq_nodes is None:
    print("警告: extract_recency接收到None节点列表")
    return {}
  
  if not seq_nodes:
    print("警告: extract_recency接收到空节点列表")
    return {}
  
  try:
    # 确保所有的last_retrieved都是整数类型
    normalized_timestamps = []
    for node in seq_nodes:
      if node is None:
        print("警告: 节点为None，跳过")
        continue
        
      if not hasattr(node, 'last_retrieved'):
        print(f"警告: 节点 {node} 没有last_retrieved属性，使用默认值0")
        normalized_timestamps.append(0)
        continue
        
      if isinstance(node.last_retrieved, str):
        try:
          normalized_timestamps.append(int(node.last_retrieved))
        except ValueError:
          # 如果无法转换为整数，使用0作为默认值
          normalized_timestamps.append(0)
      else:
        normalized_timestamps.append(node.last_retrieved)
    
    if not normalized_timestamps:
      return {node.node_id: 1.0 for node in seq_nodes if node is not None and hasattr(node, 'node_id')}
      
    max_timestep = max(normalized_timestamps)
  
    recency_decay = 0.99
    recency_out = dict()
    for count, node in enumerate(seq_nodes): 
      if node is None or not hasattr(node, 'node_id') or not hasattr(node, 'last_retrieved'):
        continue
        
      # 获取标准化后的时间戳
      try:
        last_retrieved = normalized_timestamps[count]
        recency_out[node.node_id] = (recency_decay
                                    ** (max_timestep - last_retrieved))
      except Exception as e:
        print(f"计算节点 {node.node_id} 的recency时出错: {str(e)}")
        # 使用默认值
        recency_out[node.node_id] = 1.0
  
    return recency_out
  except Exception as e:
    print(f"extract_recency处理节点列表时出错: {str(e)}")
    # 返回一个默认字典
    return {node.node_id: 1.0 for node in seq_nodes if node is not None and hasattr(node, 'node_id')}


def extract_importance(seq_nodes):
  """
  Gets the current Persona object and a list of nodes that are in a 
  chronological order, and outputs a dictionary that has the importance score
  calculated.

  Parameters: 
    seq_nodes: A list of Node object in a chronological order. 
  Returns: 
    importance_out: A dictionary whose keys are the node.node_id and whose 
                    values are the float that represents the importance score.
  """
  # 检查seq_nodes是否为None或为空
  if seq_nodes is None:
    print("警告: extract_importance接收到None节点列表")
    return {}
  
  if not seq_nodes:
    print("警告: extract_importance接收到空节点列表")
    return {}
  
  try:
    importance_out = dict()
    for count, node in enumerate(seq_nodes): 
      if node is None:
        print("警告: 节点为None，跳过")
        continue
        
      if not hasattr(node, 'node_id') or not hasattr(node, 'importance'):
        print(f"警告: 节点缺少必要属性，跳过")
        continue
        
      # 确保importance是数值类型
      if isinstance(node.importance, str):
        try:
          importance_out[node.node_id] = float(node.importance)
        except ValueError:
          # 如果无法转换为数值，使用默认值
          print(f"警告: 节点 {node.node_id} 的importance无法转换为数值，使用默认值")
          importance_out[node.node_id] = 50.0
      else:
        importance_out[node.node_id] = node.importance
  
    return importance_out
  except Exception as e:
    print(f"extract_importance处理节点列表时出错: {str(e)}")
    # 返回一个默认字典
    return {node.node_id: 50.0 for node in seq_nodes if node is not None and hasattr(node, 'node_id')}


def extract_relevance(seq_nodes, embeddings, focal_pt): 
  """
  Gets the current Persona object, a list of seq_nodes that are in a 
  chronological order, and the focal_pt string and outputs a dictionary 
  that has the relevance score calculated.

  Parameters: 
    seq_nodes: A list of Node object in a chronological order. 
    focal_pt: A string describing the current thought of revent of focus.  
  Returns: 
    relevance_out: A dictionary whose keys are the node.node_id and whose 
                   values are the float that represents the relevance score.
  """
  # 确保embeddings不为None
  if embeddings is None:
    print("警告: embeddings为None，使用空字典代替")
    embeddings = {}
    
  try:
    focal_embedding = get_text_embedding(focal_pt)
  except Exception as e:
    print(f"获取焦点嵌入向量时出错: {str(e)}")
    # 如果无法获取嵌入向量，返回默认值
    return {node.node_id: 0.5 for node in seq_nodes}

  relevance_out = dict()
  for count, node in enumerate(seq_nodes): 
    try:
      # 检查节点内容是否在embeddings中
      if node.content in embeddings:
        node_embedding = embeddings[node.content]
        # 计算余弦相似度
        relevance_out[node.node_id] = cos_sim(node_embedding, focal_embedding)
      else:
        # 如果没有对应的嵌入向量，使用默认值
        relevance_out[node.node_id] = 0.5
    except Exception as e:
      print(f"计算节点 {node.node_id} 的相关性时出错: {str(e)}")
      # 如果计算过程中出错，使用默认值
      relevance_out[node.node_id] = 0.5

  return relevance_out


# ##############################################################################
# ###                              CONCEPT NODE                              ###
# ##############################################################################

class ConceptNode: 
  def __init__(self, node_dict): 
    # Loading the content of a memory node in the memory stream. 
    self.node_id = node_dict["node_id"]
    self.node_type = node_dict["node_type"]
    self.content = node_dict["content"]
    self.importance = node_dict["importance"]
    # 确保created是整数类型
    self.created = int(node_dict["created"]) if node_dict["created"] is not None else 0
    # 确保last_retrieved是整数类型
    self.last_retrieved = int(node_dict["last_retrieved"]) if node_dict["last_retrieved"] is not None else 0
    self.pointer_id = node_dict["pointer_id"]


  def package(self): 
    """
    Packaging the ConceptNode 

    Parameters:
      None
    Returns: 
      packaged dictionary
    """
    curr_package = {}
    curr_package["node_id"] = self.node_id
    curr_package["node_type"] = self.node_type
    curr_package["content"] = self.content
    curr_package["importance"] = self.importance
    curr_package["created"] = self.created
    curr_package["last_retrieved"] = self.last_retrieved
    curr_package["pointer_id"] = self.pointer_id

    return curr_package


# ##############################################################################
# ###                             MEMORY STREAM                              ###
# ##############################################################################

class MemoryStream: 
  def __init__(self, nodes, embeddings): 
    # Loading the memory stream for the agent. 
    self.seq_nodes = []
    self.id_to_node = dict()
    for node in nodes: 
      new_node = ConceptNode(node)
      self.seq_nodes += [new_node]
      self.id_to_node[new_node.node_id] = new_node

    self.embeddings = embeddings


  def count_observations(self): 
    """
    Counting the number of observations (basically, the number of all nodes in 
    memory stream except for the reflections)

    Parameters:
      None
    Returns: 
      Count
    """
    count = 0
    for i in self.seq_nodes: 
      if i.node_type == "observation": 
        count += 1
    return count


  def retrieve(self, focal_points, time_step, n_count=120, curr_filter="all",
               hp=[0, 1, 0.5], stateless=False, verbose=False): 
    """
    Retrieve elements from the memory stream. 

    Parameters:
      focal_points: This is the query sentence. It is in a list form where 
        the elemnts of the list are the query sentences.
      time_step: Current time_step 
      n_count: The number of nodes that we want to retrieve. 
      curr_filter: Filtering the node.type that we want to retrieve. 
        Acceptable values are 'all', 'reflection', 'observation' 
      hp: Hyperparameter for [recency_w, relevance_w, importance_w]
      verbose: verbose
    Returns: 
      retrieved: A dictionary whose keys are a focal_pt query str, and whose
        values are a list of nodes that are retrieved for that query str. 
    """
    curr_nodes = []

    # If the memory stream is empty, we return an empty dictionary.
    if len(self.seq_nodes) == 0:
      return dict()

    # Filtering for the desired node type. curr_filter can be one of the three
    # elements: 'all', 'reflection', 'observation' 
    if curr_filter == "all": 
      curr_nodes = self.seq_nodes
    else: 
      for curr_node in self.seq_nodes: 
        if curr_node.node_type == curr_filter: 
          curr_nodes += [curr_node]

    # 确保embeddings不为None
    if self.embeddings is None:
      print("警告: 在retrieve方法中，embeddings为None，初始化为空字典")
      self.embeddings = {}

    # <retrieved> is the main dictionary that we are returning
    retrieved = dict() 
    for focal_pt in focal_points: 
      # Calculating the component dictionaries and normalizing them.
      x = extract_recency(curr_nodes)
      recency_out = normalize_dict_floats(x, 0, 1)
      x = extract_importance(curr_nodes)
      importance_out = normalize_dict_floats(x, 0, 1)  
      x = extract_relevance(curr_nodes, self.embeddings, focal_pt)
      relevance_out = normalize_dict_floats(x, 0, 1)
      
      # Computing the final scores that combines the component values. 
      master_out = dict()
      for key in recency_out.keys(): 
        recency_w = hp[0]
        relevance_w = hp[1]
        importance_w = hp[2]
        master_out[key] = (recency_w * recency_out[key]
                         + relevance_w * relevance_out[key] 
                         + importance_w * importance_out[key])

      if verbose: 
        master_out = top_highest_x_values(master_out, len(master_out.keys()))
        for key, val in master_out.items(): 
          print (self.id_to_node[key].content, val)
          print (recency_w*recency_out[key]*1, 
                 relevance_w*relevance_out[key]*1, 
                 importance_w*importance_out[key]*1)

      # Extracting the highest x values.
      # <master_out> has the key of node.id and value of float. Once we get  
      # the highest x values, we want to translate the node.id into nodes 
      # and return the list of nodes.
      master_out = top_highest_x_values(master_out, n_count)
      master_nodes = [self.id_to_node[key] for key in list(master_out.keys())]

      # **Sort the master_nodes list by last_retrieved in descending order**
      master_nodes = sorted(master_nodes, key=lambda node: node.created, reverse=False)

      # We do not want to update the last retrieved time_step for these nodes
      # if we are in a stateless mode. 
      if not stateless: 
        for n in master_nodes: 
          n.last_retrieved = time_step
        
      retrieved[focal_pt] = master_nodes
    
    return retrieved 


  def _add_node(self, time_step, node_type, content, importance, pointer_id):
    """
    Adding a new node to the memory stream. 

    Parameters:
      time_step: Current time_step 
      node_type: type of node -- it's either reflection, observation
      content: the str content of the memory record
      importance: int score of the importance score
      pointer_id: the str of the parent node 
    Returns: 
      retrieved: A dictionary whose keys are a focal_pt query str, and whose
        values are a list of nodes that are retrieved for that query str. 
    """
    node_dict = dict()
    node_dict["node_id"] = len(self.seq_nodes)
    node_dict["node_type"] = node_type
    node_dict["content"] = content
    node_dict["importance"] = importance
    node_dict["created"] = time_step
    node_dict["last_retrieved"] = time_step
    node_dict["pointer_id"] = pointer_id
    new_node = ConceptNode(node_dict)

    self.seq_nodes += [new_node]
    self.id_to_node[new_node.node_id] = new_node
    
    # 确保embeddings不为None
    if self.embeddings is None:
        self.embeddings = {}
    
    try:
        self.embeddings[content] = get_text_embedding(content)
    except Exception as e:
        print(f"获取文本嵌入时出错: {str(e)}")
        # 如果获取嵌入失败，使用空列表代替
        self.embeddings[content] = []


  def remember(self, content, time_step=0):
    score = generate_importance_score([content])[0]
    self._add_node(time_step, "observation", content, score, None)


  def reflect(self, anchor, reflection_count=5, 
              retrieval_count=120, time_step=0): 
    records = self.retrieve([anchor], time_step, retrieval_count)[anchor]
    record_ids = [i.node_id for i in records]
    reflections = generate_reflection(records, anchor, reflection_count)
    scores = generate_importance_score(reflections)

    for count, reflection in enumerate(reflections): 
      self._add_node(time_step, "reflection", reflections[count], 
                     scores[count], record_ids)
