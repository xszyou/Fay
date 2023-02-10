from utils import config_util as cfg
from ai_module.yuan1_0.yuan1_0_dialog import Yuan1Dialog

def question(text):
    account = cfg.key_yuan_1_0_account
    phone = cfg.key_yuan_1_0_phone
    yuan1_dialog = Yuan1Dialog(account, phone)
    prompt = text
    a_msg = yuan1_dialog.dialog(prompt)
    return a_msg
