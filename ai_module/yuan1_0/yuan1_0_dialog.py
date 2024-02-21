from simhash import Simhash
from ai_module.yuan1_0.inspurai import Yuan, set_yuan_account,Example
import heapq
import sys
from utils import config_util as cfg

class Yuan1Dialog:
    def __init__(self, account, phone) -> None:
        self.account = account
        self.phone = phone
        set_yuan_account(account, phone)
        self.yuan = Yuan(engine='dialog',
            input_prefix="问：“",
            input_suffix="”",
            output_prefix="答：“",
            output_suffix="”",
            max_tokens=30,
            append_output_prefix_to_query=True)
        self.h_dialog = []

    def get_relative_qa(self, prompt, h_dialog, topN=2):
        """
        可以添加相关性计算，这里简单使用最近的一次对话。
        :topN: 需要返回的相关对话轮数。
        """
        def simhash(query, text,):
            """
            采用局部敏感的hash值表示语义。
            """
            q_simhash = Simhash(query)
            t_simhash = Simhash(text)
            max_hashbit = max(len(bin(q_simhash.value)), len(bin(t_simhash.value)))

            distance = q_simhash.distance(t_simhash)
            # print(distance)

            similar = 1 - distance / max_hashbit
            return similar
        
        h_num = len(h_dialog)
        sim_values = []
        tm_effs= []
        rel_effs = []
        gamma = 0.8 # time effect coefficient

        if not h_dialog:
            return []
        else:
            for indx, dialog in enumerate(h_dialog):
                text = '|'.join((dialog.input, dialog.output))
                sim_value = simhash(prompt, text)
                tm_eff = gamma ** ((h_num - indx)/h_num)
                rel_eff = sim_value * tm_eff
                sim_values.append(sim_value)
                tm_effs.append(tm_eff)
                rel_effs.append(rel_eff)
            
            top_idx = heapq.nlargest(topN, range(len(rel_effs)), rel_effs.__getitem__)
            mst_dialog = [h_dialog[idx] for idx in top_idx]
            mst_dialog.reverse()
            return mst_dialog

    def update_example(self, yuan, exs):
        ex_ids = []
        for ex in exs:
            ex_ids.append(ex.get_id())
            yuan.add_example(ex)
        return yuan, ex_ids

    def dialog(self, prompt):
        yuan = self.yuan
        h_dialog = self.h_dialog
        exs = self.get_relative_qa(prompt, h_dialog)
        yuan, ex_ids = self.update_example(yuan, exs)
        response = yuan.submit_API(prompt=prompt, trun="。")
        if len(h_dialog)<10:    # 设置保存最多不超过10轮最近的历史对话
            h_dialog.append(Example(inp=prompt,out=response))
        else:
            del(h_dialog[0])
            h_dialog.append(Example(inp=prompt,out=response))
        for ex_id in ex_ids:
            yuan.delete_example(ex_id)
        return response
    
if __name__ == "__main__":
    cfg.load_config()
    account = cfg.key_yuan_1_0_account
    phone = cfg.key_yuan_1_0_phone
    yuan1_dialog = Yuan1Dialog(account, phone)
    prompt = "你好"
    print(yuan1_dialog.dialog(prompt))
    
