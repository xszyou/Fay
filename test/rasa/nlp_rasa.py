import json
import requests

def question(cont):
    url="http://localhost:5005/webhooks/rest/webhook"
    req = json.dumps({"sender": "user", "message": cont})
    headers = {'content-type': 'application/json'}
    r = requests.post(url, headers=headers, data=req)
    a = json.loads(r.text)[0].get('text')
    return a
