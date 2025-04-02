import json
import re


def extract_first_json_dict(input_str):
  try:
    # Replace curly quotes with standard double quotes
    input_str = (input_str.replace("“", "\"")
                          .replace("”", "\"")
                          .replace("‘", "'")
                          .replace("’", "'"))
    
    # Find the first occurrence of '{' in the input_str
    start_index = input_str.index('{')
    
    # Initialize a count to keep track of open and close braces
    count = 1
    end_index = start_index + 1
    
    # Loop to find the closing '}' for the first JSON dictionary
    while count > 0 and end_index < len(input_str):
        if input_str[end_index] == '{':
            count += 1
        elif input_str[end_index] == '}':
            count -= 1
        end_index += 1
    
    # Extract the JSON substring
    json_str = input_str[start_index:end_index]
    
    # Parse the JSON string into a Python dictionary
    json_dict = json.loads(json_str)
    
    return json_dict
  except ValueError:
    # Handle the case where the JSON parsing fails
    return None


def extract_first_json_dict_categorical(input_str): 
  reasoning_pattern = r'"Reasoning":\s*"([^"]+)"'
  response_pattern = r'"Response":\s*"([^"]+)"'

  reasonings = re.findall(reasoning_pattern, input_str)
  responses = re.findall(response_pattern, input_str)

  return responses, reasonings


def extract_first_json_dict_numerical(input_str): 
  reasoning_pattern = re.compile(r'"Reasoning":\s*"([^"]+)"')
  response_pattern = re.compile(r'"Response":\s*(\d+\.?\d*)')

  reasonings = reasoning_pattern.findall(input_str)
  responses = response_pattern.findall(input_str)
  return responses, reasonings

