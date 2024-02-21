import torch
from ringrwkv.configuration_rwkv_world import RwkvConfig
from ringrwkv.rwkv_tokenizer import TRIE_TOKENIZER
from ringrwkv.modehf_world import RwkvForCausalLM

model = RwkvForCausalLM.from_pretrained("RWKV-4-World-1.5B")
#model = RwkvForCausalLM.from_pretrained("RWKV-4-World-3B")
#model = RwkvForCausalLM.from_pretrained("RWKV-4-World-0.4B")
tokenizer = TRIE_TOKENIZER('./ringrwkv/rwkv_vocab_v20230424.txt')

data = ""
def question(cont):
    global data
    prompt = data + f'Question: {cont.strip()}\n\nAnswer:'
    input_ids = tokenizer.encode(prompt)
    input_ids = torch.tensor(input_ids).unsqueeze(0)
    out = model.generate(input_ids,max_new_tokens=20)

    outlist = out[0].tolist()
    for i  in outlist:
        if i==0:
            outlist.remove(i)
    answer = tokenizer.decode(outlist)
    # data = answer + "\n\n"
    answer = answer.replace(prompt, "", 1)
    return answer


