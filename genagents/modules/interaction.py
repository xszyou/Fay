import math
import sys
import datetime
import random
import string
import re
import os

from numpy import dot
from numpy.linalg import norm

from simulation_engine.settings import * 
from simulation_engine.global_methods import *
from simulation_engine.gpt_structure import *
from simulation_engine.llm_json_parser import *
from utils import util

def _main_agent_desc(agent, anchor): 
  agent_desc = ""
  agent_desc += f"Self description: {agent.get_self_description()}\n==\n"
  agent_desc += f"Other observations about the subject:\n\n"

  retrieved = agent.memory_stream.retrieve([anchor], 0, n_count=120)
  if len(retrieved) == 0:
    return agent_desc
  nodes = list(retrieved.values())[0]
  for node in nodes:
    agent_desc += f"{node.content}\n"
  return agent_desc


def _utterance_agent_desc(agent, anchor): 
  agent_desc = ""
  agent_desc += f"Self description: {agent.get_self_description()}\n==\n"
  agent_desc += f"Other observations about the subject:\n\n"

  retrieved = agent.memory_stream.retrieve([anchor], 0, n_count=120)
  if len(retrieved) == 0:
    return agent_desc
  
  nodes = list(retrieved.values())[0]
  for node in nodes:
    agent_desc += f"{node.content}\n"
  return agent_desc


def run_gpt_generate_categorical_resp(
  agent_desc, 
  questions,
  prompt_version="1",
  gpt_version="GPT4o",  
  verbose=False):

  def create_prompt_input(agent_desc, questions):
    str_questions = ""
    for key, val in questions.items(): 
      str_questions += f"Q: {key}\n"
      str_questions += f"Option: {val}\n\n"
    str_questions = str_questions.strip()
    return [agent_desc, str_questions]

  def _func_clean_up(gpt_response, prompt=""): 
    responses, reasonings = extract_first_json_dict_categorical(gpt_response)
    ret = {"responses": responses, "reasonings": reasonings}
    return ret

  def _get_fail_safe():
    return None

  if len(questions) > 1: 
    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/interaction/categorical_resp/batch_v1.txt" 
  else: 
    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/interaction/categorical_resp/singular_v1.txt" 

  prompt_input = create_prompt_input(agent_desc, questions) 
  fail_safe = _get_fail_safe() 

  output, prompt, prompt_input, fail_safe = chat_safe_generate(
    prompt_input, prompt_lib_file, gpt_version, 1, fail_safe, 
    _func_clean_up, verbose)

  return output, [output, prompt, prompt_input, fail_safe]


def categorical_resp(agent, questions): 
  anchor = " ".join(list(questions.keys()))
  agent_desc = _main_agent_desc(agent, anchor)
  return run_gpt_generate_categorical_resp(
           agent_desc, questions, "1", LLM_VERS)[0]


def run_gpt_generate_numerical_resp(
  agent_desc, 
  questions, 
  float_resp,
  prompt_version="1",
  gpt_version="GPT4o",  
  verbose=False):

  def create_prompt_input(agent_desc, questions, float_resp):
    str_questions = ""
    for key, val in questions.items(): 
      str_questions += f"Q: {key}\n"
      str_questions += f"Range: {str(val)}\n\n"
    str_questions = str_questions.strip()

    if float_resp: 
      resp_type = "float"
    else: 
      resp_type = "integer"
    return [agent_desc, str_questions, resp_type]

  def _func_clean_up(gpt_response, prompt=""): 
    responses, reasonings = extract_first_json_dict_numerical(gpt_response)
    ret = {"responses": responses, "reasonings": reasonings}
    return ret

  def _get_fail_safe():
    return None

  if len(questions) > 1: 
    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/interaction/numerical_resp/batch_v1.txt" 
  else: 
    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/interaction/numerical_resp/singular_v1.txt" 

  prompt_input = create_prompt_input(agent_desc, questions, float_resp) 
  fail_safe = _get_fail_safe() 

  output, prompt, prompt_input, fail_safe = chat_safe_generate(
    prompt_input, prompt_lib_file, gpt_version, 1, fail_safe, 
    _func_clean_up, verbose)

  if float_resp: 
    output["responses"] = [float(i) for i in output["responses"]]
  else: 
    output["responses"] = [int(i) for i in output["responses"]]

  return output, [output, prompt, prompt_input, fail_safe]


def numerical_resp(agent, questions, float_resp): 
  anchor = " ".join(list(questions.keys()))
  agent_desc = _main_agent_desc(agent, anchor)
  return run_gpt_generate_numerical_resp(
           agent_desc, questions, float_resp, "1", LLM_VERS)[0]


def run_gpt_generate_utterance(
  agent_desc, 
  str_dialogue,
  context,
  prompt_version="1",
  gpt_version="GPT4o",  
  verbose=False):
  """
  运行GPT生成对话回复
  
  参数:
    agent_desc: 代理描述
    str_dialogue: 对话字符串
    context: 上下文
    prompt_version: 提示版本，默认为"1"
    gpt_version: GPT版本，默认为"GPT4o"
    verbose: 是否输出详细信息，默认为False
    
  返回:
    output: 生成的回复
    详细信息: [output, prompt, prompt_input, fail_safe]
  """
  def create_prompt_input(agent_desc, str_dialogue, context):
    return [agent_desc, context, str_dialogue]

  def _func_clean_up(gpt_response, prompt=""): 
    try:
      # 确保gpt_response是字符串类型
      if not isinstance(gpt_response, str):
        util.log(1, f"GPT响应不是字符串类型: {type(gpt_response)}")
        return "抱歉，我现在太忙了，休息一会，请稍后再试。"
      
      # 提取JSON字典
      json_dict = extract_first_json_dict(gpt_response)
      if json_dict is None or "utterance" not in json_dict:
        util.log(1, f"无法从GPT响应中提取有效的JSON或缺少utterance字段: {gpt_response[:100]}...")
        return "抱歉，我现在太忙了，休息一会，请稍后再试。"
      
      # 返回utterance字段
      return json_dict["utterance"]
    except Exception as e:
      util.log(1, f"处理GPT响应时出错: {str(e)}")
      return "抱歉，我现在太忙了，休息一会，请稍后再试。"

  def _get_fail_safe():
    return "对不起，我现在无法回答这个问题。"

  # 确保模板文件路径正确
  prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/interaction/utternace/utterance_v1.txt" 
  if not os.path.exists(prompt_lib_file):
    util.log(1, f"模板文件不存在: {prompt_lib_file}")
    return "抱歉，我现在太忙了，休息一会，请稍后再试。", ["抱歉，我现在太忙了，休息一会，请稍后再试。", "", [], ""]

  prompt_input = create_prompt_input(agent_desc, str_dialogue, context) 
  fail_safe = _get_fail_safe() 

  # 调用chat_safe_generate函数生成回复
  try:
    output, prompt, prompt_input, fail_safe = chat_safe_generate(
      prompt_input, prompt_lib_file, gpt_version, 1, fail_safe,
      _func_clean_up, verbose)
    
    # 确保输出是字符串类型
    if output is None:
      util.log(1, "GPT生成的输出为None")
      output = fail_safe
  except Exception as e:
    util.log(1, f"调用chat_safe_generate时出错: {str(e)}")
    output = fail_safe
    prompt = ""
    prompt_input = []

  return output, [output, prompt, prompt_input, fail_safe]


def utterance(agent, curr_dialogue, context): 
  str_dialogue = ""
  for row in curr_dialogue:
    str_dialogue += f"[{row[0]}]: {row[1]}\n"
  str_dialogue += f"[{agent.get_fullname()}]: [Fill in]\n"

  anchor = str_dialogue
  agent_desc = _utterance_agent_desc(agent, anchor)
  return run_gpt_generate_utterance(
           agent_desc, str_dialogue, context, "1", LLM_VERS, False)[0]

##  Ask function.
def run_gpt_generate_ask(
    agent_desc,
    questions,
    prompt_version="1",
    gpt_version="GPT4o",
    verbose=False):

    def create_prompt_input(agent_desc, questions):
        str_questions = ""
        i = 1
        for q in questions:
            str_questions += f"Q{i}: {q['question']}\n"
            str_questions += f"Type: {q['response-type']}\n"
            if q['response-type'] == 'categorical':
                str_questions += f"Options: {', '.join(q['response-options'])}\n"
            elif q['response-type'] in ['int', 'float']:
                str_questions += f"Range: {q['response-scale']}\n"
            elif q['response-type'] == 'open':
                char_limit = q.get('response-char-limit', 200)
                str_questions += f"Character Limit: {char_limit}\n"
            str_questions += "\n"
            i += 1
        return [agent_desc, str_questions.strip()]

    def _func_clean_up(gpt_response, prompt=""):
        responses = extract_first_json_dict(gpt_response)
        return responses

    def _get_fail_safe():
        return None

    prompt_lib_file = f"{LLM_PROMPT_DIR}/generative_agent/interaction/ask/batch_v1.txt"

    prompt_input = create_prompt_input(agent_desc, questions)
    fail_safe = _get_fail_safe()

    output, prompt, prompt_input, fail_safe = chat_safe_generate(
        prompt_input, prompt_lib_file, gpt_version, 1, fail_safe,
        _func_clean_up, verbose)

    return output, [output, prompt, prompt_input, fail_safe]



  
