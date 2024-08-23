import logging

from PyQt5.QtCore import pyqtSignal, QObject, QSettings, Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QMenu, QAction, QStyledItemDelegate, QAbstractItemView

from asyncua import ua
from asyncua.sync import SyncNode, new_node

from uawidgets.utils import trycatchslot
from uawidgets.get_node_dialog import GetNodeTextButton


logger = logging.getLogger(__name__)


class HistoryWidget(QObject):

    error = pyqtSignal(Exception)
    history_changed = pyqtSignal(SyncNode)

    def __init__(self, view):
        self.view = view
        QObject.__init__(self, view)
        self.model = QStandardItemModel()

        delegate = MyDelegate(self.view, self)
        delegate.error.connect(self.error.emit)
        delegate.history_changed.connect(self.history_changed.emit)
        self.view.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.view.setModel(self.model)
        self.view.setItemDelegate(delegate)
        self.settings = QSettings()
        self.model.setHorizontalHeaderLabels(['DonutType', 'NodeId', "BrowseName", "TypeDefinition"])
        state = self.settings.value("WindowState/history_widget_state", None)
        if state is not None:
            self.view.horizontalHeader().restoreState(state)
        self.view.horizontalHeader().setSectionResizeMode(0)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.node = None

        self.reloadAction = QAction("Reload", self.model)
        self.reloadAction.triggered.connect(self.reload)
        self.addHistroyAction = QAction("Add History", self.model)
        self.addHistroyAction.triggered.connect(self.add_history)
        self.removeHistoryAction = QAction("Remove History", self.model)
        self.removeHistoryAction.triggered.connect(self.remove_history)

        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.showContextMenu)
        self._contextMenu = QMenu()
        self._contextMenu.addAction(self.reloadAction)
        self._contextMenu.addSeparator()
        self._contextMenu.addAction(self.addHistroyAction)
        self._contextMenu.addAction(self.removeHistoryAction)

    def showContextMenu(self, position):
        if not self.node:
            return
        self.removeRefAction.setEnabled(False)
        idx = self.view.currentIndex()
        if idx.isValid():
            self.removeRefAction.setEnabled(True)
        self._contextMenu.exec_(self.view.viewport().mapToGlobal(position))

    def clear(self):
        # remove all rows but not header!!
        self.model.removeRows(0, self.model.rowCount())
        self.node = None

    def _make_default_history(self):
        #FIXME: remeber last choosen values or use values that make sense
        ref = ua.ReferenceDescription() #TODO: Brauch man das
        return ref

    @trycatchslot
    def add_history(self):
        ref = self._make_default_history()
        logger.info("Adding history: %s", ref)
        self._add_ref_history(ref)
        idx = self.model.index(self.model.rowCount() - 1, 0)
        self.view.setCurrentIndex(idx)
        #self.view.edit(idx)

    @trycatchslot
    def reload(self):
        node = self.node
        self.clear()
        self.show_history(node)

    @trycatchslot
    def remove_history(self):
        idx = self.view.currentIndex()
        if not idx.isValid():
            logger.warning("No valid reference selected to remove")
        idx = idx.sibling(idx.row(), 0)
        item = self.model.itemFromIndex(idx)
        ref = item.data(Qt.UserRole)
        self.do_remove_history(ref)
        self.reload()

    def do_remove_history(self, ref, check=True):
        logger.info("Removing: %s", ref)
        it = ua.DeleteReferencesItem()
        it.SourceNodeId = self.node.nodeid
        it.ReferenceTypeId = ref.ReferenceTypeId
        it.IsForward = ref.IsForward
        it.TargetNodeId = ref.NodeId
        it.DeleteBidirectional = False
        #param = ua.DeleteReferencesParameters()
        #param.ReferencesToDelete.append(it)
        results = self.node.server.delete_references([it])
        logger.info("Remove result: %s", results[0])
        if check:
            results[0].check()

    def save_state(self):
        self.settings.setValue("WindowState/history_widget_state", self.view.horizontalHeader().saveState())

    def show_history(self, node):
        self.clear()
        self.node = node
        self._show_history(node)

    def _show_history(self, node):
        try:
            refs = node.get_children_descriptions(refs=ua.ObjectIds.References)
        except Exception as ex:
            self.error.emit(ex)
            raise
        for ref in refs:
            self._add_ref_history(ref)

    def _add_ref_history(self, ref):
        if ref.ReferenceTypeId.Identifier in ua.ObjectIdNames:
            typename = ua.ObjectIdNames[ref.ReferenceTypeId.Identifier]
        else:
            typename = str(ref.ReferenceTypeId)
        nodeid = ref.NodeId.to_string()
        if ref.NodeId.NamespaceIndex == 0 and ref.NodeId.Identifier in ua.ObjectIdNames:
            nodeid += ": " + ua.ObjectIdNames[ref.NodeId.Identifier]
        if ref.TypeDefinition.Identifier in ua.ObjectIdNames:
            typedef = ua.ObjectIdNames[ref.TypeDefinition.Identifier]
        else:
            typedef = ref.TypeDefinition.to_string()
        titem = QStandardItem(typename)
        titem.setData(ref, Qt.UserRole)
        self.model.appendRow([
            titem,
            QStandardItem(nodeid),
            QStandardItem(ref.BrowseName.to_string()),
            QStandardItem(typedef)
        ])


class MyDelegate(QStyledItemDelegate):

    error = pyqtSignal(Exception)
    history_changed = pyqtSignal(SyncNode)


    def __init__(self, parent, widget):
        QStyledItemDelegate.__init__(self, parent)
        self._widget = widget

    @trycatchslot
    def createEditor(self, parent, option, idx):
        if idx.column() > 1:
            return None
        data_idx = idx.sibling(idx.row(), 0)
        item = self._widget.model.itemFromIndex(data_idx)
        ref = item.data(Qt.UserRole)
        if idx.column() == 1:
            node = new_node(self._widget.node, ref.NodeId)
            startnode = new_node(self._widget.node, ua.ObjectIds.RootFolder)
            button = GetNodeTextButton(parent, node, startnode)
            return button
        elif idx.column() == 0:
            node = new_node(self._widget.node, ref.ReferenceTypeId)
            startnode = new_node(self._widget.node, ua.ObjectIds.ReferenceTypesFolder)
            button = GetNodeTextButton(parent, node, startnode)
            return button

    @trycatchslot
    def setModelData(self, editor, model, idx):
        data_idx = idx.sibling(idx.row(), 0)
        ref = model.data(data_idx, Qt.UserRole)
        self._widget.do_remove_history(ref, check=False)
        if idx.column() == 0:
            ref.ReferenceTypeId = editor.get_node().nodeid
            model.setData(idx, ref.ReferenceTypeId.to_string(), Qt.DisplayRole)
        elif idx.column() == 1:
            ref.NodeId = editor.get_node().nodeid
            ref.NodeClass = editor.get_node().get_node_class()
            model.setData(idx, ref.NodeId.to_string(), Qt.DisplayRole)
        model.setData(data_idx, ref, Qt.UserRole)
        if ref.NodeId.is_null() or ref.ReferenceTypeId.is_null():
            logger.info("Do not save yet. Need NodeId and ReferenceTypeId to be set")
            return
        self._write_ref(ref)

    def _write_ref(self, ref):
        logger.info("Writing ref %s", ref)
        it = ua.AddReferencesItem()
        it.SourceNodeId = self._widget.node.nodeid
        it.ReferenceTypeId = ref.ReferenceTypeId
        it.IsForward = ref.IsForward
        it.TargetNodeId = ref.NodeId
        it.TargetNodeClass = ref.NodeClass

        results = self._widget.node.server.add_references([it])
        results[0].check()

        self.history_changed.emit(self._widget.node)
        self._widget.reload()




