import os

import time

from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtCore import *
from PyQt5 import QtWidgets

from scheduler.thread_manager import MyThread


class MainWindow(QMainWindow):
    SigSendMessageToJS = pyqtSignal(str)

    def __init__(self):
        super(MainWindow, self).__init__()
        # self.setWindowFlags(Qt.WindowType.WindowShadeButtonHint)
        self.setWindowTitle('FeiFei Alpha')
        # self.setFixedSize(16 * 80, 9 * 80) 
        self.setGeometry(0, 0, 16 * 70, 9 * 70)
        self.showMaximized()
        # self.center()
        self.browser = QWebEngineView()
        #清空缓存
        profile = QWebEngineProfile.defaultProfile()
        profile.clearHttpCache()  
        self.browser.load(QUrl('http://127.0.0.1:5000'))
        self.setCentralWidget(self.browser)
        MyThread(target=self.runnable).start()

    def runnable(self):
        while True:
            if not self.isVisible():
                # try:
                #     wsa_server.get_instance().stop_server()
                #     wsa_server.get_web_instance().stop_server()
                #     thread_manager.stopAll()
                # except BaseException as e:
                #     print(e)
                os.system("taskkill /F /PID {}".format(os.getpid()))
            time.sleep(0.05)

    def center(self):
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

    def keyPressEvent(self, event):
        pass
        # if event.key() == Qt.Key_F12:
        #     self.s = TDevWindow()
        #     self.s.show()
        #     self.browser.page().setDevToolsPage(self.s.mpJSWebView.page())

    def OnReceiveMessageFromJS(self, strParameter):
        if not strParameter:
            return


class TDevWindow(QDialog):
    def __init__(self):
        super(TDevWindow, self).__init__()
        self.init_ui()

    def init_ui(self):
        self.mpJSWebView = QWebEngineView(self)
        self.url = 'https://www.baidu.com/'
        self.mpJSWebView.page().load(QUrl(self.url))
        self.mpJSWebView.show()

        self.pJSTotalVLayout = QVBoxLayout()
        self.pJSTotalVLayout.setSpacing(0)
        self.pJSTotalVLayout.addWidget(self.mpJSWebView)
        self.pWebGroup = QGroupBox('Web View', self)
        self.pWebGroup.setLayout(self.pJSTotalVLayout)

        self.mainLayout = QHBoxLayout()
        self.mainLayout.setSpacing(5)
        self.mainLayout.addWidget(self.pWebGroup)
        self.setLayout(self.mainLayout)
        self.setMinimumSize(800, 800)