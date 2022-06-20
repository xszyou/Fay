import os
import sys

from PyQt5 import QtGui
from PyQt5.QtWidgets import QApplication

from ai_module import ali_nls
from core import wsa_server
from gui import flask_server
from gui.window import MainWindow
from utils import config_util


def __clear_samples():
    if not os.path.exists("./samples"):
        os.mkdir("./samples")
    for file_name in os.listdir('./samples'):
        if file_name.startswith('sample-') and file_name.endswith('.mp3'):
            os.remove('./samples/' + file_name)


if __name__ == '__main__':
    __clear_samples()
    config_util.load_config()
    # fay_booter.start()
    ws_server = wsa_server.new_instance(port=10002)
    ws_server.start_server()
    web_ws_server = wsa_server.new_web_instance(port=10003)
    web_ws_server.start_server()

    ali_nls.start()

    flask_server.start()
    # MyThread(target=runnable).start()
    app = QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon('icon.png'))
    win = MainWindow()
    win.show()
    app.exit(app.exec_())
