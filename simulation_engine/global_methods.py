import random
import json
import string
import csv
import datetime as dt
import os
import numpy
import math
import shutil, errno

from os import listdir


def create_folder_if_not_there(curr_path): 
  """
  Checks if a folder in the curr_path exists. If it does not exist, creates
  the folder. 
  Note that if the curr_path designates a file location, it will operate on 
  the folder that contains the file. But the function also works even if the 
  path designates to just a folder. 
  Args:
    curr_list: list to write. The list comes in the following form:
               [['key1', 'val1-1', 'val1-2'...],
                ['key2', 'val2-1', 'val2-2'...],]
    outfile: name of the csv file to write    
  RETURNS: 
    True: if a new folder is created
    False: if a new folder is not created
  """
  outfolder_name = curr_path.split("/")
  if len(outfolder_name) != 1: 
    # This checks if the curr path is a file or a folder. 
    if "." in outfolder_name[-1]: 
      outfolder_name = outfolder_name[:-1]

    outfolder_name = "/".join(outfolder_name)
    if not os.path.exists(outfolder_name):
      os.makedirs(outfolder_name)
      return True

  return False 


def write_list_of_list_to_csv(curr_list_of_list, outfile):
  """
  Writes a list of list to csv. 
  Unlike write_list_to_csv_line, it writes the entire csv in one shot. 
  ARGS:
    curr_list_of_list: list to write. The list comes in the following form:
               [['key1', 'val1-1', 'val1-2'...],
                ['key2', 'val2-1', 'val2-2'...],]
    outfile: name of the csv file to write    
  RETURNS: 
    None
  """
  create_folder_if_not_there(outfile)
  with open(outfile, "w") as f:
    writer = csv.writer(f)
    writer.writerows(curr_list_of_list)


def write_list_to_csv_line(line_list, outfile): 
  """
  Writes one line to a csv file.
  Unlike write_list_of_list_to_csv, this opens an existing outfile and then 
  appends a line to that file. 
  This also works if the file does not exist already. 
  ARGS:
    curr_list: list to write. The list comes in the following form:
               ['key1', 'val1-1', 'val1-2'...]
               Importantly, this is NOT a list of list. 
    outfile: name of the csv file to write   
  RETURNS: 
    None
  """
  create_folder_if_not_there(outfile)

  # Opening the file first so we can write incrementally as we progress
  curr_file = open(outfile, 'a',)
  csvfile_1 = csv.writer(curr_file)
  csvfile_1.writerow(line_list)
  curr_file.close()


def read_file_to_list(curr_file, header=False, strip_trail=True): 
  """
  Reads in a csv file to a list of list. If header is True, it returns a 
  tuple with (header row, all rows)
  ARGS:
    curr_file: path to the current csv file. 
  RETURNS: 
    List of list where the component lists are the rows of the file. 
  """
  if not header: 
    analysis_list = []
    with open(curr_file) as f_analysis_file: 
      data_reader = csv.reader(f_analysis_file, delimiter=",")
      for count, row in enumerate(data_reader): 
        if strip_trail: 
          row = [i.strip() for i in row]
        analysis_list += [row]
    return analysis_list
  else: 
    analysis_list = []
    with open(curr_file) as f_analysis_file: 
      data_reader = csv.reader(f_analysis_file, delimiter=",")
      for count, row in enumerate(data_reader): 
        if strip_trail: 
          row = [i.strip() for i in row]
        analysis_list += [row]
    return analysis_list[0], analysis_list[1:]


def read_file_to_set(curr_file, col=0): 
  """
  Reads in a "single column" of a csv file to a set. 
  ARGS:
    curr_file: path to the current csv file. 
  RETURNS: 
    Set with all items in a single column of a csv file. 
  """
  analysis_set = set()
  with open(curr_file) as f_analysis_file: 
    data_reader = csv.reader(f_analysis_file, delimiter=",")
    for count, row in enumerate(data_reader): 
      analysis_set.add(row[col])
  return analysis_set


def get_row_len(curr_file): 
  """
  Get the number of rows in a csv file 
  ARGS:
    curr_file: path to the current csv file. 
  RETURNS: 
    The number of rows
    False if the file does not exist
  """
  try: 
    analysis_set = set()
    with open(curr_file) as f_analysis_file: 
      data_reader = csv.reader(f_analysis_file, delimiter=",")
      for count, row in enumerate(data_reader): 
        analysis_set.add(row[0])
    return len(analysis_set)
  except: 
    return False


def check_if_file_exists(curr_file): 
  """
  Checks if a file exists
  ARGS:
    curr_file: path to the current csv file. 
  RETURNS: 
    True if the file exists
    False if the file does not exist
  """
  try: 
    with open(curr_file) as f_analysis_file: pass
    return True
  except: 
    return False


def find_filenames(path_to_dir, suffix=".csv"):
  """
  Given a directory, find all files that ends with the provided suffix and 
  returns their paths.  
  ARGS:
    path_to_dir: Path to the current directory 
    suffix: The target suffix.
  RETURNS: 
    A list of paths to all files in the directory. 
  """
  filenames = listdir(path_to_dir)
  new_filenames = []
  for i in filenames: 
    if ".DS_Store" not in i: 
      new_filenames += [i]
  filenames = new_filenames
  return [ path_to_dir+"/"+filename 
           for filename in filenames if filename.endswith( suffix ) ]


def average(list_of_val): 
  """
  Finds the average of the numbers in a list.
  ARGS:
    list_of_val: a list of numeric values  
  RETURNS: 
    The average of the values
  """
  try: 
    list_of_val = [float(i) for i in list_of_val if not math.isnan(i)]
    return sum(list_of_val)/float(len(list_of_val))
  except: 
    return float('nan')


def std(list_of_val): 
  """
  Finds the std of the numbers in a list.
  ARGS:
    list_of_val: a list of numeric values  
  RETURNS: 
    The std of the values
  """
  try: 
    list_of_val = [float(i) for i in list_of_val if not math.isnan(i)]
    std = numpy.std(list_of_val)
    return std
  except: 
    return float('nan')


def copyanything(src, dst):
  """
  Copy over everything in the src folder to dst folder. 
  ARGS:
    src: address of the source folder  
    dst: address of the destination folder  
  RETURNS: 
    None
  """
  try:
    shutil.copytree(src, dst)
  except OSError as exc: # python >2.5
    if exc.errno in (errno.ENOTDIR, errno.EINVAL):
      shutil.copy(src, dst)
    else: raise


def generate_alphanumeric_string(length):
  characters = string.ascii_letters + string.digits
  result = ''.join(random.choice(characters) for _ in range(length))
  return result


def extract_first_json_dict(input_str):
  """
  从字符串中提取第一个JSON字典
  
  参数:
    input_str: 包含JSON字典的字符串
    
  返回:
    解析后的JSON字典，如果解析失败则返回None
  """
  try:
    # 确保输入是字符串类型
    if not isinstance(input_str, str):
      print("提取JSON错误: 输入必须是字符串类型")
      return None
      
    # 替换特殊引号为标准双引号
    input_str = (input_str.replace(""", "\"")
                        .replace(""", "\"")
                        .replace("'", "'")
                        .replace("'", "'"))
    
    # 查找第一个'{'的位置
    try:
      start_index = input_str.index('{')
    except ValueError:
      print("提取JSON错误: 未找到JSON开始标记'{'")
      return None
    
    # 初始化计数器，用于跟踪开闭括号
    count = 1
    end_index = start_index + 1
    
    # 循环查找与第一个'{'匹配的'}'
    while count > 0 and end_index < len(input_str):
      if input_str[end_index] == '{':
        count += 1
      elif input_str[end_index] == '}':
        count -= 1
      end_index += 1
    
    # 如果没有找到匹配的'}'
    if count > 0:
      print("提取JSON错误: JSON格式不完整，缺少匹配的'}'")
      return None
    
    # 提取JSON子字符串
    json_str = input_str[start_index:end_index]
    
    # 解析JSON字符串为Python字典
    try:
      json_dict = json.loads(json_str)
      return json_dict
    except json.JSONDecodeError as e:
      print(f"解析JSON错误: {str(e)}")
      return None
  except Exception as e:
    # 处理所有其他异常
    print(f"提取JSON时发生错误: {str(e)}")
    return None


def read_file_to_string(file_path):
  try:
    with open(file_path, 'r', encoding='utf-8') as file:
      content = file.read()
    return content
  except FileNotFoundError:
    return "The file was not found."
  except Exception as e:
    return str(e)


def write_string_to_file(full_path, text_content):
  create_folder_if_not_there(full_path)
  import os
  try:
    with open(full_path, 'w', encoding='utf-8') as file:
        file.write(text_content)
    return f"File successfully written to {full_path}"
  except Exception as e:
    return str(e)


def chunk_list(lst, q_chunk_size):
  """
  Splits the given list into sublists of specified chunk size.

  Parameters:
  lst (list): The list to be split into chunks.
  q_chunk_size (int): The size of each chunk.

  Returns:
  list: A list of sublists where each sublist has a length of q_chunk_size.
  """
  # Initialize the result list
  chunked_list = []
  
  # Loop through the list in steps of q_chunk_size
  for i in range(0, len(lst), q_chunk_size):
    # Append the sublist to the result list
    chunked_list.append(lst[i:i + q_chunk_size])

  return chunked_list


def write_dict_to_json(data, filename):
    """
    Writes a dictionary to a JSON file.

    Parameters:
    data (dict): The dictionary to write to the JSON file.
    filename (str): The name of the file to write the JSON data to.
    """
    try:
        # 确保目录存在
        directory = os.path.dirname(filename)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        
        # 使用UTF-8编码写入JSON文件
        with open(filename, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"写入JSON文件时出错: {str(e)}")


def read_json_to_dict(file_path):
    """
    Reads a JSON file and converts it to a Python dictionary.

    Parameters:
    file_path (str): The path to the JSON file.

    Returns:
    dict: The content of the JSON file as a dictionary.
    """
    try:
        # 使用UTF-8编码读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"未找到文件: {file_path}")
    except json.JSONDecodeError:
        print(f"解析JSON文件出错: {file_path}")
    except Exception as e:
        print(f"发生错误: {str(e)}")
