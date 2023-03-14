from flask import Flask
from flask_cors import CORS
from gevent import pywsgi

app = Flask("test_server")
CORS(app, supports_credentials=True)

@app.route('/', methods=['get'])
def abc():
    return 'hello world'

server = pywsgi.WSGIServer(('0.0.0.0',5000), app)
server.serve_forever()