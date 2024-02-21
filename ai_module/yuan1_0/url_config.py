import requests
import hashlib
import time
from datetime import datetime
import pytz
import json
import os

ACCOUNT = ''
PHONE = ''

SUBMIT_URL = "http://api-air.inspur.com:32102/v1/interface/api/infer/getRequestId?"
REPLY_URL = "http://api-air.inspur.com:32102/v1/interface/api/result?"


def code_md5(str):
    code=str.encode("utf-8")
    m = hashlib.md5()
    m.update(code)
    result= m.hexdigest()
    return result

def rest_get(url, header,timeout, show_error=False):
    '''Call rest get method'''
    try:
        response = requests.get(url, headers=header,timeout=timeout, verify=False)
        return response
    except Exception as exception:
        if show_error:
            print(exception)
        return None

def header_generation():
    """Generate header for API request."""
    t = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d")
    global ACCOUNT, PHONE
    ACCOUNT, PHONE = os.environ.get('YUAN_ACCOUNT').split('||')
    token=code_md5(ACCOUNT+PHONE+t)
    headers = {'token': token}
    return headers

def submit_request(query,temperature,topP,topK,max_tokens,engine, frequencyPenalty,responsePenalty,noRepeatNgramSize):
    """Submit query to the backend server and get requestID."""
    headers=header_generation()
    # url=SUBMIT_URL + "account={0}&data={1}&temperature={2}&topP={3}&topK={4}&tokensToGenerate={5}&type={6}".format(ACCOUNT,query,temperature,topP,topK,max_tokens,"api")
    # url=SUBMIT_URL + "engine={0}&account={1}&data={2}&temperature={3}&topP={4}&topK={5}&tokensToGenerate={6}" \
    #                  "&type={7}".format(engine,ACCOUNT,query,temperature,topP,topK, max_tokens,"api")
    url=SUBMIT_URL + "engine={0}&account={1}&data={2}&temperature={3}&topP={4}&topK={5}&tokensToGenerate={6}" \
                     "&type={7}&frequencyPenalty={8}&responsePenalty={9}&noRepeatNgramSize={10}".\
        format(engine,ACCOUNT,query,temperature,topP,topK, max_tokens,"api", frequencyPenalty,responsePenalty,noRepeatNgramSize)
    response=rest_get(url,headers,30)
    response_text = json.loads(response.text)
    if  response_text["flag"]:
        requestId = response_text["resData"]
        return requestId
    else:
        raise  RuntimeWarning(response_text)

def reply_request(requestId,cycle_count=5):
    """Check reply API to get the inference response."""
    url = REPLY_URL + "account={0}&requestId={1}".format(ACCOUNT, requestId)
    headers=header_generation()
    response_text= {"flag":True, "resData":None}
    for i in range(cycle_count):
        response = rest_get(url, headers, 30, show_error=True)
        response_text = json.loads(response.text)
        if response_text["resData"] != None:
            return response_text
        if response_text["flag"] == False and i ==cycle_count-1:
            raise  RuntimeWarning(response_text)
        time.sleep(3)
    return response_text
