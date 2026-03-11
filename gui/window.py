import os
import sys
import time

from PyQt5 import QtWidgets
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineProfile, QWebEngineView
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
)

from scheduler.thread_manager import stopAll


def _resolve_runtime_dir():
    if getattr(sys, "frozen", False):
        return os.path.abspath(os.path.dirname(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


class MainWindow(QMainWindow):
    SigSendMessageToJS = pyqtSignal(str)

    def __init__(self):
        super(MainWindow, self).__init__()
        self._allow_close = False
        self._shutdown_in_progress = False
        self._tray_hint_shown = False
        self._tray_icon = None

        self.setWindowTitle("FeiFei Alpha")
        self.setGeometry(0, 0, 16 * 70, 9 * 70)
        self.showMaximized()

        self.browser = QWebEngineView()
        profile = QWebEngineProfile.defaultProfile()
        profile.clearHttpCache()
        self.browser.load(QUrl("http://127.0.0.1:5000"))
        self.setCentralWidget(self.browser)

        self._init_tray_icon()

    def _resolve_app_icon(self):
        runtime_dir = _resolve_runtime_dir()
        for icon_name in ("favicon.ico", "icon.png"):
            icon_path = os.path.join(runtime_dir, icon_name)
            if os.path.exists(icon_path):
                return QIcon(icon_path)
        return self.windowIcon()

    def _init_tray_icon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        tray_icon = QSystemTrayIcon(self)
        tray_icon.setIcon(self._resolve_app_icon())
        tray_icon.setToolTip("Fay")

        tray_menu = QMenu(self)
        show_action = QAction("Open Fay", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_from_tray)
        tray_menu.addAction(exit_action)

        tray_icon.setContextMenu(tray_menu)
        tray_icon.activated.connect(self._on_tray_icon_activated)
        tray_icon.show()
        self._tray_icon = tray_icon

    def _show_tray_message_once(self):
        if self._tray_icon is None or self._tray_hint_shown:
            return
        self._tray_hint_shown = True
        self._tray_icon.showMessage(
            "Fay",
            "Window minimized to tray. Double-click the tray icon to restore it.",
            QSystemTrayIcon.Information,
            3000,
        )

    def _shutdown_services(self):
        if self._shutdown_in_progress:
            return

        self._shutdown_in_progress = True
        try:
            import fay_booter

            if fay_booter.is_running():
                print("Stopping Fay services...")
                fay_booter.stop()
                time.sleep(0.5)
        except BaseException as exc:
            print(f"Failed to stop Fay services: {exc}")

        try:
            stopAll()
        except BaseException as exc:
            print(f"Failed to stop background threads: {exc}")

    def show_from_tray(self):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def exit_from_tray(self):
        self._allow_close = True
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self._shutdown_services()
        QApplication.instance().quit()
        os._exit(0)

    def _on_tray_icon_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_from_tray()

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return

        if self._tray_icon is None:
            event.ignore()
            self.exit_from_tray()
            return

        event.ignore()
        self.hide()
        self._show_tray_message_once()

    def center(self):
        screen = QtWidgets.QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

    def keyPressEvent(self, event):
        pass

    def OnReceiveMessageFromJS(self, strParameter):
        if not strParameter:
            return


class TDevWindow(QDialog):
    def __init__(self):
        super(TDevWindow, self).__init__()
        self.init_ui()

    def init_ui(self):
        self.mpJSWebView = QWebEngineView(self)
        self.url = "https://www.baidu.com/"
        self.mpJSWebView.page().load(QUrl(self.url))
        self.mpJSWebView.show()

        self.pJSTotalVLayout = QVBoxLayout()
        self.pJSTotalVLayout.setSpacing(0)
        self.pJSTotalVLayout.addWidget(self.mpJSWebView)
        self.pWebGroup = QGroupBox("Web View", self)
        self.pWebGroup.setLayout(self.pJSTotalVLayout)

        self.mainLayout = QHBoxLayout()
        self.mainLayout.setSpacing(5)
        self.mainLayout.addWidget(self.pWebGroup)
        self.setLayout(self.mainLayout)
        self.setMinimumSize(800, 800)
