from utils import config_util as cfg
import openai

def question(text):
    cfg.load_config()
    openai.api_key = cfg.key_chatgpt_api_key
    prompt = text
    completions = openai.Completion.create(engine="text-davinci-002", prompt=prompt, max_tokens=1024)
    a_msg = completions.choices[0].text
    return a_msg
