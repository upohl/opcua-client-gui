#! /usr/bin/env python3

import sys
from pathlib import Path

from datetime import datetime
import logging

from PyQt5.QtCore import (
    pyqtSignal,
    QFile,
    QTimer,
    Qt,
    QObject,
    QSettings,
    QTextStream,
    QItemSelection,
    QCoreApplication,
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt5.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QWidget,
    QApplication,
    QLineEdit,
    QMenu,
    QDialog,
    QInputDialog,
)

from asyncua import ua
from asyncua.sync import SyncNode

from uaclient.uaclient import UaClient
from uaclient.mainwindow_ui import Ui_MainWindow
from uaclient.connection_dialog import ConnectionDialog
from uaclient.application_certificate_dialog import ApplicationCertificateDialog
from uaclient.graphwidget import GraphUI

from uawidgets.attrs_widget import AttrsWidget
from uawidgets.tree_widget import TreeWidget
from uawidgets.refs_widget import RefsWidget
from uawidgets.utils import trycatchslot
from uawidgets.logger import QtHandler
from uawidgets.call_method_dialog import CallMethodDialog

from uaclient.duckdb_logger import DuckDBLogger

logger = logging.getLogger(__name__)

class DataChangeHandler(QObject):
    data_change_fired = pyqtSignal(object, str, str)

    def datachange_notification(self, node, val, data):
        if data.monitored_item.Value.SourceTimestamp:
            dato = data.monitored_item.Value.SourceTimestamp.isoformat()
        elif data.monitored_item.Value.ServerTimestamp:
            dato = data.monitored_item.Value.ServerTimestamp.isoformat()
        else:
            dato = datetime.now().isoformat()
        self.data_change_fired.emit(node, str(val), dato)

class EventHandler(QObject):
    event_fired = pyqtSignal(object)

    def event_notification(self, event):
        self.event_fired.emit(event)

class EventUI(object):

    def __init__(self, window, uaclient, logger):
        self.window = window
        self.uaclient = uaclient
        self._handler = EventHandler()
        self._subscribed_nodes = []  # FIXME: not really needed
        self.model = QStandardItemModel()
        self.window.ui.evView.setModel(self.model)
        self.window.ui.actionSubscribeEvent.triggered.connect(self._subscribe)
        self.window.ui.actionUnsubscribeEvents.triggered.connect(self._unsubscribe)
        # context menu
        self.window.addAction(self.window.ui.actionSubscribeEvent)
        self.window.addAction(self.window.ui.actionUnsubscribeEvents)
        self.window.addAction(self.window.ui.actionAddToGraph)
        self._handler.event_fired.connect(
            self._update_event_model, type=Qt.QueuedConnection
        )

        self.duckdb_logger = logger

        # accept drops
        self.model.canDropMimeData = self.canDropMimeData
        self.model.dropMimeData = self.dropMimeData

    def canDropMimeData(self, mdata, action, row, column, parent):
        return True

    def show_error(self, *args):
        self.window.show_error(*args)

    def dropMimeData(self, mdata, action, row, column, parent):
        node = self.uaclient.client.get_node(mdata.text())
        self._subscribe(node)
        return True

    def clear(self):
        self._subscribed_nodes = []
        self.model.clear()

    @trycatchslot
    def _subscribe(self, node=None):
        logger.info("Subscribing to %s", node)
        if not node:
            node = self.window.get_current_node()
            if node is None:
                return
        if node in self._subscribed_nodes:
            logger.info("already subscribed to event for node: %s", node)
            return
        self.window.check_duckdb_connection_before_subcribe()
        logger.info("Subscribing to events for %s", node)
        self.window.ui.evDockWidget.raise_()
        try:
            self.uaclient.subscribe_events(node, self._handler)
        except Exception as ex:
            self.window.show_error(ex)
            raise
        else:
            self._subscribed_nodes.append(node)

    @trycatchslot
    def _unsubscribe(self):
        node = self.window.get_current_node()
        if node is None:
            return
        self._subscribed_nodes.remove(node)
        self.uaclient.unsubscribe_events(node)
        self.window.check_duckdb_connection_after_unsubcribe()

    @trycatchslot
    def _update_event_model(self, event):
        self.model.appendRow([QStandardItem(str(event))])
        self.log_duckdb(str(event), datetime.now())

    def log_duckdb(self, event, timestamp):
        if self.duckdb_logger:
            self.duckdb_logger.log_event(
                event, timestamp, self.window.server_uri
            )
        else:
            print("DuckDB logger not initialized. Please set up logging first.")

class DataChangeUI(object):

    def __init__(self, window, uaclient, logger):
        self.window = window
        self.uaclient = uaclient
        self._subhandler = DataChangeHandler()
        self._subscribed_nodes = []
        self.model = QStandardItemModel()
        self.window.ui.subView.setModel(self.model)
        self.window.ui.subView.horizontalHeader().setSectionResizeMode(1)

        self.duckdb_logger = logger

        self.window.ui.actionSubscribeDataChange.triggered.connect(self._subscribe)
        self.window.ui.actionUnsubscribeDataChange.triggered.connect(self._unsubscribe)

        # populate contextual menu
        self.window.addAction(self.window.ui.actionSubscribeDataChange)
        self.window.addAction(self.window.ui.actionUnsubscribeDataChange)

        # handle subscriptions
        self._subhandler.data_change_fired.connect(
            self._update_subscription_model, type=Qt.QueuedConnection
        )

        # accept drops
        self.model.canDropMimeData = self.canDropMimeData
        self.model.dropMimeData = self.dropMimeData

    def canDropMimeData(self, mdata, action, row, column, parent):
        return True

    def dropMimeData(self, mdata, action, row, column, parent):
        node = self.uaclient.client.get_node(mdata.text())
        self._subscribe(node)
        return True

    def clear(self):
        self._subscribed_nodes = []
        self.model.clear()

    def show_error(self, *args):
        self.window.show_error(*args)

    @trycatchslot
    def _subscribe(self, node=None):
        if not isinstance(node, SyncNode):
            node = self.window.get_current_node()
            if node is None:
                return
        if node in self._subscribed_nodes:
            logger.warning("allready subscribed to node: %s ", node)
            return
        self.window.check_duckdb_connection_before_subcribe()
        self.model.setHorizontalHeaderLabels(["DisplayName", "Value", "Timestamp"])
        text = str(node.read_display_name().Text)
        row = [QStandardItem(text), QStandardItem("No Data yet"), QStandardItem("")]
        row[0].setData(node)
        self.model.appendRow(row)
        self._subscribed_nodes.append(node)
        self.window.ui.subDockWidget.raise_()
        try:
            self.uaclient.subscribe_datachange(node, self._subhandler)
        except Exception as ex:
            self.window.show_error(ex)
            idx = self.model.indexFromItem(row[0])
            self.model.takeRow(idx.row())
            raise

    @trycatchslot
    def _unsubscribe(self):
        node = self.window.get_current_node()
        if node is None:
            return
        self.uaclient.unsubscribe_datachange(node)
        self._subscribed_nodes.remove(node)
        i = 0
        while self.model.item(i):
            item = self.model.item(i)
            if item.data() == node:
                self.model.removeRow(i)
            i += 1
        self.window.check_duckdb_connection_after_unsubcribe()

    def _update_subscription_model(self, node, value, timestamp):
        i = 0
        while self.model.item(i):
            item = self.model.item(i)
            if item.data() == node:
                it = self.model.item(i, 1)
                it.setText(value)
                it_ts = self.model.item(i, 2)
                it_ts.setText(timestamp)
                # added duckdb logging
                self.log_duckdb(
                    display_name=str(node.read_display_name().Text),
                    node_id=node.nodeid.to_string(),
                    value=value,
                    data_type=str(node.get_data_type_as_variant_type()),
                    timestamp=timestamp,
                )
            i += 1

    def log_duckdb(self, display_name, node_id, value, data_type, timestamp):
        if self.duckdb_logger:
            self.duckdb_logger.log_data(
                display_name, node_id, value, data_type, timestamp, self.window.server_uri
            )
        else:
            print("DuckDB logger not initialized. Please set up logging first.")

    def closeEvent(self, event):
        if hasattr(self, "duckdb_logger") and self.duckdb_logger:
            self.duckdb_logger.close()
        # ... any other cleanup code ...
        super().closeEvent(event)

class StaticDataUI(object):

    def __init__(self, window, logger):
        self.window = window
        self.model = QStandardItemModel()
        self.window.ui.staticDataView.setModel(self.model)
        self.window.ui.staticDataView.horizontalHeader().setSectionResizeMode(1)

        self.model.setHorizontalHeaderLabels(['timestamp', 'name', "node_id", "value", "server"])

        self.duckdb_logger = logger

        self.window.ui.buttonRefresh.clicked.connect(self.refresh)

        self.result = self.duckdb_logger.get_last_10_data(self.window.default_duckdb_path)

        self.refresh()

        self.timer = QTimer()
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def refresh(self):
        self.result = self.duckdb_logger.get_last_10_data(self.window.default_duckdb_path)
        if self.result is None:
            return
        self.clear()
        for item in self.result:
            self.model.appendRow([QStandardItem(str(item[0])), QStandardItem(str(item[1])), QStandardItem(str(item[2])),
                                  QStandardItem(str(item[3])), QStandardItem(str(item[4]))])

    def clear(self):
        # remove all rows but not header!!
        self.model.removeRows(0, self.model.rowCount())
        self.node = None



class Window(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Connect the new action
        self.ui.actionSetupDuckDBLogging.triggered.connect(self.setup_duckdb_dialog)

        self.setWindowIcon(QIcon(":/network.svg"))

        # ... existing initialization code ...
        self.duckdb_logger = None

        # Initialize DuckDBLogger with default path
        self.default_duckdb_path = self.get_default_duckdb_path()
        self.setup_duckdb_logging()

        # fix stuff imposible to do in qtdesigner
        # remove dock titlebar for addressbar
        w = QWidget()
        self.ui.addrDockWidget.setTitleBarWidget(w)
        # tabify some docks
        self.tabifyDockWidget(self.ui.evDockWidget, self.ui.subDockWidget)
        self.tabifyDockWidget(self.ui.subDockWidget, self.ui.refDockWidget)
        self.tabifyDockWidget(self.ui.refDockWidget, self.ui.graphDockWidget)
        self.tabifyDockWidget(self.ui.graphDockWidget, self.ui.staticDataDockWidget)

        # we only show statusbar in case of errors
        self.ui.statusBar.hide()

        # setup QSettings for application and get a settings object
        QCoreApplication.setOrganizationName("FreeOpcUa")
        QCoreApplication.setApplicationName("OpcUaClient")
        self.settings = QSettings()
        self.server_uri = ""
        self.settings.setValue(
            "address_list",
            [
                "opc.tcp://127.0.0.1:4840",
                "opc.tcp://opcua.umati.app:4840",
                "opc.tcp://vm-388d63f4.test-server.ag:4840",
                "opc.tcp://localhost.ag:4840",
                "opc.tcp://localhost:53530/OPCUA/SimulationServer/",
            ],
        )
        self._address_list = self.settings.value(
            "address_list",
            [
                "opc.tcp://127.0.0.1:4840",
                "opc.tcp://opcua.umati.app:4840",
                "opc.tcp://vm-388d63f4.test-server.ag:4840",
                "opc.tcp://localhost.ag:4840",
                "opc.tcp://localhost:53530/OPCUA/SimulationServer/",
            ],
        )
        print("ADR", self._address_list)
        self._address_list_max_count = int(
            self.settings.value("address_list_max_count", 10)
        )

        # init widgets
        for addr in self._address_list:
            self.ui.addrComboBox.insertItem(100, addr)

        self.uaclient = UaClient()

        self.tree_ui = TreeWidget(self.ui.treeView)
        self.tree_ui.error.connect(self.show_error)
        self.setup_context_menu_tree()
        self.ui.treeView.selectionModel().currentChanged.connect(
            self._update_actions_state
        )

        self.refs_ui = RefsWidget(self.ui.refView)
        self.refs_ui.error.connect(self.show_error)
        self.attrs_ui = AttrsWidget(self.ui.attrView)
        self.attrs_ui.error.connect(self.show_error)
        self.datachange_ui = DataChangeUI(self, self.uaclient, self.duckdb_logger)
        self.event_ui = EventUI(self, self.uaclient, self.duckdb_logger)
        self.graph_ui = GraphUI(self, self.uaclient)
        self.static_ui = StaticDataUI(self, self.duckdb_logger)

        self.ui.addrComboBox.currentTextChanged.connect(self._uri_changed)
        self._uri_changed(
            self.ui.addrComboBox.currentText()
        )  # force update for current value at startup

        self.ui.treeView.selectionModel().selectionChanged.connect(self.show_refs)
        self.ui.actionCopyPath.triggered.connect(self.tree_ui.copy_path)
        self.ui.actionCopyNodeId.triggered.connect(self.tree_ui.copy_nodeid)
        self.ui.actionCall.triggered.connect(self.call_method)

        self.ui.treeView.selectionModel().selectionChanged.connect(self.show_attrs)
        self.ui.attrRefreshButton.clicked.connect(self.show_attrs)

        self.resize(
            int(self.settings.value("main_window_width", 800)),
            int(self.settings.value("main_window_height", 600)),
        )
        data = self.settings.value("main_window_state", None)
        if data:
            self.restoreState(data)

        self.ui.connectButton.clicked.connect(self.connect)
        self.ui.disconnectButton.clicked.connect(self.disconnect)
        # self.ui.treeView.expanded.connect(self._fit)

        self.ui.actionConnect.triggered.connect(self.connect)
        self.ui.actionDisconnect.triggered.connect(self.disconnect)

        self.ui.connectOptionButton.clicked.connect(self.show_connection_dialog)
        self.ui.actionClient_Application_Certificate.triggered.connect(
            self.show_application_certificate_dialog
        )
        self.ui.actionDark_Mode.triggered.connect(self.dark_mode)

    def get_default_duckdb_path(self):
        home_dir = Path.home()
        return str(home_dir / "opcua.duckdb")

    def setup_duckdb_dialog(self):
        default_path = self.get_default_duckdb_path()
        db_path, ok = QInputDialog.getText(
            self,
            "DuckDB Setup",
            "Enter DuckDB file path:",
            QLineEdit.Normal,
            default_path,
        )
        if ok:
            if not db_path:  # If the user cleared the input, use the default path
                db_path = default_path
            self.setup_duckdb_logging(db_path)
            QMessageBox.information(
                self,
                "DuckDB Setup",
                f"DuckDB logging configured successfully!\nPath: {db_path}",
            )

    def setup_duckdb_logging(self):
        if self.duckdb_logger:
            self.duckdb_logger.close()  # Close existing connection if any
        self.duckdb_logger = DuckDBLogger()

    def _uri_changed(self, uri):
        self.uaclient.load_security_settings(uri)

    def show_connection_dialog(self):
        dia = ConnectionDialog(self, self.ui.addrComboBox.currentText())
        dia.security_mode = self.uaclient.security_mode
        dia.security_policy = self.uaclient.security_policy
        dia.certificate_path = self.uaclient.user_certificate_path
        dia.private_key_path = self.uaclient.user_private_key_path
        ret = dia.exec_()
        if ret:
            self.uaclient.security_mode = dia.security_mode
            self.uaclient.security_policy = dia.security_policy
            self.uaclient.user_certificate_path = dia.certificate_path
            self.uaclient.user_private_key_path = dia.private_key_path

    def show_application_certificate_dialog(self):
        dia = ApplicationCertificateDialog(self)
        dia.certificate_path = self.uaclient.application_certificate_path
        dia.private_key_path = self.uaclient.application_private_key_path
        ret = dia.exec_()
        if ret == QDialog.Accepted:
            self.uaclient.application_certificate_path = dia.certificate_path
            self.uaclient.application_private_key_path = dia.private_key_path
        self.uaclient.save_application_certificate_settings()

    @trycatchslot
    def show_refs(self, selection):
        if isinstance(selection, QItemSelection):
            if not selection.indexes():  # no selection
                return

        node = self.get_current_node()
        if node:
            self.refs_ui.show_refs(node)

    @trycatchslot
    def show_attrs(self, selection):
        if isinstance(selection, QItemSelection):
            if not selection.indexes():  # no selection
                return

        node = self.get_current_node()
        if node:
            self.attrs_ui.show_attrs(node)

    def show_error(self, msg):
        logger.warning("showing error: %s")
        self.ui.statusBar.show()
        self.ui.statusBar.setStyleSheet(
            "QStatusBar { background-color : red; color : black; }"
        )
        self.ui.statusBar.showMessage(str(msg))
        QTimer.singleShot(1500, self.ui.statusBar.hide)

    def get_current_node(self, idx=None):
        return self.tree_ui.get_current_node(idx)

    def get_uaclient(self):
        return self.uaclient

    @trycatchslot
    def connect(self):
        uri = self.ui.addrComboBox.currentText()
        uri = uri.strip()
        self.server_uri = uri
        try:
            self.uaclient.connect(uri)
        except Exception as ex:
            self.show_error(ex)
            raise

        self._update_address_list(uri)
        self.tree_ui.set_root_node(self.uaclient.client.nodes.root)
        self.ui.treeView.setFocus()
        self.load_current_node()

    def _update_address_list(self, uri):
        if uri == self._address_list[0]:
            return
        if uri in self._address_list:
            self._address_list.remove(uri)
        self._address_list.insert(0, uri)
        if len(self._address_list) > self._address_list_max_count:
            self._address_list.pop(-1)

    def disconnect(self):
        try:
            self.uaclient.disconnect()
        except Exception as ex:
            self.show_error(ex)
            raise
        finally:
            self.save_current_node()
            self.tree_ui.clear()
            self.refs_ui.clear()
            self.attrs_ui.clear()
            self.datachange_ui.clear()
            self.event_ui.clear()
            self.duckdb_logger.close()

    def closeEvent(self, event):
        self.tree_ui.save_state()
        self.attrs_ui.save_state()
        self.refs_ui.save_state()
        self.settings.setValue("main_window_width", self.size().width())
        self.settings.setValue("main_window_height", self.size().height())
        self.settings.setValue("main_window_state", self.saveState())
        self.settings.setValue("address_list", self._address_list)
        self.disconnect()
        event.accept()

    def save_current_node(self):
        current_node = self.tree_ui.get_current_node()
        if current_node:
            mysettings = self.settings.value("current_node", None)
            if mysettings is None:
                mysettings = {}
            uri = self.ui.addrComboBox.currentText()
            mysettings[uri] = current_node.nodeid.to_string()
            self.settings.setValue("current_node", mysettings)

    def load_current_node(self):
        mysettings = self.settings.value("current_node", None)
        if mysettings is None:
            return
        uri = self.ui.addrComboBox.currentText()
        if uri in mysettings:
            nodeid = ua.NodeId.from_string(mysettings[uri])
            node = self.uaclient.client.get_node(nodeid)
            self.tree_ui.expand_to_node(node)

    def setup_context_menu_tree(self):
        self.ui.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeView.customContextMenuRequested.connect(
            self._show_context_menu_tree
        )
        self._contextMenu = QMenu()
        self.addAction(self.ui.actionCopyPath)
        self.addAction(self.ui.actionCopyNodeId)
        self._contextMenu.addSeparator()
        self._contextMenu.addAction(self.ui.actionCall)
        self._contextMenu.addSeparator()

    def addAction(self, action):
        self._contextMenu.addAction(action)

    @trycatchslot
    def _update_actions_state(self, current, previous):
        node = self.get_current_node(current)
        self.ui.actionCall.setEnabled(False)
        if node:
            if node.read_node_class() == ua.NodeClass.Method:
                self.ui.actionCall.setEnabled(True)

    def _show_context_menu_tree(self, position):
        node = self.tree_ui.get_current_node()
        if node:
            self._contextMenu.exec_(self.ui.treeView.viewport().mapToGlobal(position))

    def call_method(self):
        node = self.get_current_node()
        dia = CallMethodDialog(self, self.uaclient.client, node)
        dia.show()

    def dark_mode(self):
        self.settings.setValue("dark_mode", self.ui.actionDark_Mode.isChecked())

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Restart for changes to take effect")
        msg.exec_()

    # Checks if there is no datachange or eventchange subscribtion. If there is not, the duckdb logger gets closed
    def check_duckdb_connection_after_unsubcribe(self):
        if len(self.event_ui._subscribed_nodes) == 0 and len(self.datachange_ui._subscribed_nodes) == 0:
            self.duckdb_logger.close()

    def check_if_sub_list_empty(self):
        if len(self.event_ui._subscribed_nodes) == 0 and len(self.datachange_ui._subscribed_nodes) == 0:
            return True
        return False

    # checksn if there is a duckdblogger connection before a subscription
    def check_duckdb_connection_before_subcribe(self):
        if not self.duckdb_logger.check_if_open()==True:
            self.duckdb_logger.connect(self.default_duckdb_path)

def main():
    app = QApplication(sys.argv)
    client = Window()
    handler = QtHandler(client.ui.logTextEdit)
    logging.getLogger().addHandler(handler)
    logging.getLogger("uaclient").setLevel(logging.INFO)
    logging.getLogger("uawidgets").setLevel(logging.INFO)
    # logging.getLogger("opcua").setLevel(logging.INFO)  # to enable logging of ua client library

    # set stylesheet
    if QSettings().value("dark_mode", "false") == "true":
        file = QFile(":/dark.qss")
        file.open(QFile.ReadOnly | QFile.Text)
        stream = QTextStream(file)
        app.setStyleSheet(stream.readAll())

    client.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
