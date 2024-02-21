import os
import uuid
from ai_module.yuan1_0.url_config import submit_request, reply_request

def set_yuan_account(user, phone):
    os.environ['YUAN_ACCOUNT'] = user + '||' + phone


class Example:
    """ store some examples(input, output pairs and formats) for few-shots to prime the model."""
    def __init__(self, inp, out):
        self.input = inp
        self.output = out
        self.id = uuid.uuid4().hex

    def get_input(self):
        """return the input of the example."""
        return self.input

    def get_output(self):
        """Return the output of the example."""
        return self.output

    def get_id(self):
        """Returns the unique ID of the example."""
        return self.id

    def as_dict(self):
        return {
            "input": self.get_input(),
            "output": self.get_output(),
            "id": self.get_id(),
        }

class Yuan:
    """The main class for a user to interface with the Inspur Yuan API.
    A user can set account info and add examples of the API request.
    """

    def __init__(self, 
                engine='base_10B',
                temperature=0.9,
                max_tokens=100,
                input_prefix='',
                input_suffix='\n',
                output_prefix='答:',
                output_suffix='\n\n',
                append_output_prefix_to_query=False,
                topK=1,
                topP=0.9,
                frequencyPenalty=1.2,
                responsePenalty=1.2,
                noRepeatNgramSize=2):
        
        self.examples = {}
        self.engine = engine
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.topK = topK
        self.topP = topP
        self.frequencyPenalty = frequencyPenalty
        self.responsePenalty = responsePenalty
        self.noRepeatNgramSize = noRepeatNgramSize
        self.input_prefix = input_prefix
        self.input_suffix = input_suffix
        self.output_prefix = output_prefix
        self.output_suffix = output_suffix
        self.append_output_prefix_to_query = append_output_prefix_to_query
        self.stop = (output_suffix + input_prefix).strip()

        # if self.engine not in ['base_10B','translate','dialog']:
        #     raise Exception('engine must be one of [\'base_10B\',\'translate\',\'dialog\'] ')

    def add_example(self, ex):
        """Add an example to the object.
        Example must be an instance of the Example class."""
        assert isinstance(ex, Example), "Please create an Example object."
        self.examples[ex.get_id()] = ex

    def delete_example(self, id):
        """Delete example with the specific id."""
        if id in self.examples:
            del self.examples[id]

    def get_example(self, id):
        """Get a single example."""
        return self.examples.get(id, None)

    def get_all_examples(self):
        """Returns all examples as a list of dicts."""
        return {k: v.as_dict() for k, v in self.examples.items()}

    def get_prime_text(self):
        """Formats all examples to prime the model."""
        return "".join(
            [self.format_example(ex) for ex in self.examples.values()])

    def get_engine(self):
        """Returns the engine specified for the API."""
        return self.engine

    def get_temperature(self):
        """Returns the temperature specified for the API."""
        return self.temperature

    def get_max_tokens(self):
        """Returns the max tokens specified for the API."""
        return self.max_tokens

    def craft_query(self, prompt):
        """Creates the query for the API request."""
        q = self.get_prime_text(
        ) + self.input_prefix + prompt + self.input_suffix
        if self.append_output_prefix_to_query:
            q = q + self.output_prefix

        return q

    def format_example(self, ex):
        """Formats the input, output pair."""
        return self.input_prefix + ex.get_input(
        ) + self.input_suffix + self.output_prefix + ex.get_output(
        ) + self.output_suffix
    
    def response(self, 
                query,
                engine='base_10B',
                max_tokens=20,
                temperature=0.9,
                topP=0.1,
                topK=1,
                frequencyPenalty=1.0,
                responsePenalty=1.0,
                noRepeatNgramSize=0):
        """Obtains the original result returned by the API."""

        try:
            # requestId = submit_request(query,temperature,topP,topK,max_tokens, engine)
            requestId = submit_request(query, temperature, topP, topK, max_tokens, engine, frequencyPenalty,
                                       responsePenalty, noRepeatNgramSize)
            response_text = reply_request(requestId)
        except Exception as e:
            raise e
        
        return response_text


    def del_special_chars(self, msg):
        special_chars = ['<unk>', '<eod>', '#', '▃', '▁', '▂', '　']
        for char in special_chars:
            msg = msg.replace(char, '')
        return msg


    def submit_API(self, prompt, trun=[]):
        """Submit prompt to yuan API interface and obtain an pure text reply.
        :prompt: Question or any content a user may input.
        :return: pure text response."""
        query = self.craft_query(prompt)
        res = self.response(query,engine=self.engine,
                            max_tokens=self.max_tokens,
                            temperature=self.temperature,
                            topP=self.topP,
                            topK=self.topK,
                            frequencyPenalty = self.frequencyPenalty,
                            responsePenalty = self.responsePenalty,
                            noRepeatNgramSize = self.noRepeatNgramSize)
        if 'resData' in res and res['resData'] != None:
            txt = res['resData']
        else:
            txt = '模型返回为空，请尝试修改输入'
        # 单独针对翻译模型的后处理
        if self.engine == 'translate':
            txt = txt.replace(' ##', '').replace(' "', '"').replace(": ", ":").replace(" ,", ",") \
                .replace('英文：', '').replace('文：', '').replace("( ", "(").replace(" )", ")")
        else:
            txt = txt.replace(' ', '')
        txt = self.del_special_chars(txt)

        # trun多结束符截断模型输出
        if isinstance(trun, str):
            trun = [trun]
        try:
            if trun != None and isinstance(trun, list) and  trun != []:
                for tr in trun:
                    if tr in txt and tr!="":
                        txt = txt[:txt.index(tr)]
                    else:
                        continue
        except:
            return txt
        return txt


