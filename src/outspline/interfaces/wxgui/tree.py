# Outspline - A highly modular and extensible outliner.
# Copyright (C) 2011 Dario Giovannetti <dev@dariogiovannetti.net>
#
# This file is part of Outspline.
#
# Outspline is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Outspline is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Outspline.  If not, see <http://www.gnu.org/licenses/>.

import os
import wx
import wx.dataview as dv

from outspline.coreaux_api import Event, OutsplineError
import outspline.coreaux_api as coreaux_api
import outspline.core_api as core_api

import databases
import editor
import logs

creating_tree_event = Event()
reset_context_menu_event = Event()
popup_context_menu_event = Event()
undo_tree_event = Event()
redo_tree_event = Event()
delete_items_event = Event()

dbs = {}


class Item(object):
    # The DataViewModel needs proper objects; to *not* store simple integers
    # (e.g. the items' id's) or strings as items' objects
    def __init__(self, id_, label, properties):
        self.id_ = id_
        self.label = label
        self.properties = properties

    def get_id(self):
        return self.id_

    def get_label(self):
        return self.label

    def get_properties(self):
        return self.properties

    def set_label(self, label):
        self.label = label

    def set_properties(self, properties):
        self.properties = properties


class Model(dv.PyDataViewModel):
    def __init__(self, data, filename):
        super(Model, self).__init__()
        self.data = data
        self.filename = filename

        # The wxPython demo uses weak references for the item objects: see if
        # it can be used also in this case (bug #348)
        #self.objmapper.UseWeakRefs(True)

    def IsContainer(self, item):
        # Do not test and return core_api.has_item_children because if a child
        # is added to a previously non-container item, that item should be
        # updated too
        return True

    def GetParent(self, item):
        if not item:
            return dv.NullDataViewItem
        else:
            id_ = self.ItemToObject(item).get_id()
            pid = core_api.get_item_parent(self.filename, id_)

            if pid > 0:
                return self.ObjectToItem(self.data[pid])
            else:
                return dv.NullDataViewItem

    def GetChildren(self, parent, children):
        if not parent:
            ids = core_api.get_root_items(self.filename)
        else:
            pid = self.ItemToObject(parent).get_id()
            ids = core_api.get_item_children(self.filename, pid)

        for id_ in ids:
            children.append(self.ObjectToItem(self.data[id_]))

        return len(ids)

    def GetColumnCount(self):
        return 1

    def GetValue(self, item, col):
        # For some reason Renderer needs this to return a string, but it would
        # be more natural to just pass the Item object or the id as an integer
        # Bug #347
        return str(self.ItemToObject(item).get_id())

    '''def GetColumnType(self, col):
        # It seems not needed to override this method, it's not done in the
        # demos either
        # Besides, returning "string" here would activate the "live" search
        # feature that belongs to the native GTK widget used by DataViewCtrl
        # See also bug #349
        # https://groups.google.com/d/msg/wxpython-users/QvSesrnD38E/31l8f6AzIhAJ
        # https://groups.google.com/d/msg/wxpython-users/4nsv7x1DE-s/ljQHl9RTnuEJ
        return None'''


class Renderer(dv.PyDataViewCustomRenderer):
    def __init__(self, database, treec):
        super(Renderer, self).__init__()
        self.VMARGIN = 1
        self.GAP = 2
        self.ADDITIONAL_GAP = 4
        self.database = database

        self.deffont = treec.GetFont()
        self.fgcolor = treec.GetForegroundColour()
        self.iconfont = treec.GetFont()
        self.iconfont.SetWeight(wx.FONTWEIGHT_BOLD)

        dc = wx.MemoryDC()
        dc.SelectObject(wx.EmptyBitmap(1, 1))
        dc.SetFont(self.deffont)
        # It shouldn't matter whether characters with descent are used or not,
        # but use "pb" for safety anyway
        extent = dc.GetTextExtent("pb")
        self.needed_height = extent[1] + self.VMARGIN * 2

    def SetValue(self, value):
        self.value = value
        self.label = self.database.get_item_label(int(value))
        self.teststr, self.strdata = self.database.get_item_properties(int(
                                                                        value))
        return True

    def GetValue(self):
        return self.value

    def GetSize(self):
        label = "".join((self.teststr, self.label))
        tsize = self.GetTextExtent(label)
        gapsw = (len(self.strdata)) * self.GAP + self.ADDITIONAL_GAP
        return wx.Size(tsize.GetWidth() + gapsw, self.needed_height)

    def Render(self, rect, dc, state):
        dc.SetFont(self.iconfont)
        xoffset = rect.GetX()

        for data in self.strdata:
            dc.SetTextForeground(data[1])
            dc.DrawText(data[0], xoffset, rect.GetY() + self.VMARGIN)
            xoffset += self.GetTextExtent(data[0])[0] + self.GAP

        if self.strdata:
            xoffset += self.ADDITIONAL_GAP

        # Don't use self.RenderText as the official docs would suggest, because
        # it aligns vertically in a weird way
        dc.SetFont(self.deffont)
        dc.SetTextForeground(self.fgcolor)
        dc.DrawText(self.label, xoffset, rect.GetY() + self.VMARGIN)

        return True


class Database(wx.SplitterWindow):
    def __init__(self, filename):
        super(Database, self).__init__(wx.GetApp().nb_left,
                                                    style=wx.SP_LIVE_UPDATE)

        self.config = coreaux_api.get_interface_configuration('wxgui')
        self.sash_position = self.config.get_float("logs_sash_position")
        self.sash_gravity = 1.0 - 1.0 / self.sash_position if \
                        self.config.get_bool("logs_auto_sash_gravity") else 1

        # Prevent the window from unsplitting when dragging the sash to the
        # border
        self.SetMinimumPaneSize(20)

        self.filename = filename
        self.data = {}

    def _post_init(self):
        # The native GTK widget used by DataViewCtrl would have an internal
        # "live" search feature which steals some keyboard shortcuts: Ctrl+n,
        # Ctrl+p, Ctrl+f, Ctrl+a, Ctrl+Shift+a
        # https://groups.google.com/d/msg/wxpython-users/1sUPp766uXU/0J22mUrkzoAJ
        # Ctrl+f can be recovered with by not overriding the Model's
        # GetColumnType method
        # See also bug #349
        # See bug #260 for generic issues about DataViewCtrl
        self.treec = dv.DataViewCtrl(self, style=dv.DV_MULTIPLE |
                                                            dv.DV_NO_HEADER)

        self.cmenu = ContextMenu(self)
        self.ctabmenu = TabContextMenu(self.filename)

        self.logspanel = logs.LogsPanel(self, self.filename)
        self.dbhistory = logs.DatabaseHistory(self, self.logspanel,
                                    self.logspanel.get_panel(), self.filename,
                                    self.treec.GetBackgroundColour())

        self.properties = Properties(self.treec)
        self.base_properties = DBProperties(self.properties)

        self.accelerators = {}

        creating_tree_event.signal(filename=self.filename)

        # Initialize the icons only *after* the various plugins have added
        # their properties
        self.properties.post_init()

        # Initialize the tree only *after* instantiating the class (and
        # initilizing the icons), because actions like the creation of item
        # images rely on the filename to be in the dictionary
        for row in core_api.get_all_items(self.filename):
            self._init_item_data(row["I_id"], row["I_text"])

        self.dvmodel = Model(self.data, self.filename)
        self.treec.AssociateModel(self.dvmodel)
        # According to DataViewModel's documentation (as of September 2014)
        # its reference count must be decreased explicitly to avoid memory
        # leaks; the wxPython demo, however, doesn't do it, and if done here,
        # the application crashes with a segfault when closing all databases
        # See also bug #104
        #self.dvmodel.DecRef()

        dvrenderer = Renderer(self, self.treec)
        dvcolumn = dv.DataViewColumn("Item", dvrenderer, 0,
                                                        align=wx.ALIGN_LEFT)
        self.treec.AppendColumn(dvcolumn)

        self._init_accelerators()

        self.Initialize(self.treec)

        # Initialize the logs panel *after* signalling creating_tree_event,
        # which is used to add plugin logs
        self.logspanel.initialize()

        nb_left = wx.GetApp().nb_left
        nb_left.add_page(self, os.path.basename(self.filename), select=True)

        # The logs panel must be shown only *after* adding the page to the
        # notebook, otherwise *for*some*reason* the databases opened
        # automatically by the sessions manager (those opened manually aren't
        # affected) will have the sash of the SplitterWindow not correctly
        # positioned (only if using SetSashGravity)
        if wx.GetApp().logs_configuration.is_shown():
            self.show_logs()

        self.history_item_update_requests = []
        self.history_tree_reset_request = False

        # Explicitly set focus on the tree, otherwise after opening a database
        # no window has focus, and this e.g. prevents F10 from showing the menu
        # if set on autohide, until a window is manually focused (note that
        # this would happen only when opening a database manually, it wouldn't
        # happen when a database is opened automatically by the session
        # manager)
        self.treec.SetFocus()

        self.treec.Bind(dv.EVT_DATAVIEW_ITEM_CONTEXT_MENU,
                                                        self._popup_item_menu)

        core_api.bind_to_insert_item(self._handle_insert_item)
        core_api.bind_to_update_item_text(self._handle_update_item_text)
        core_api.bind_to_deleting_item(self._handle_deleting_item)
        core_api.bind_to_deleted_item_2(self._handle_deleted_item)
        core_api.bind_to_history_insert(self._handle_history_insert)
        core_api.bind_to_history_update_simple(
                                            self._handle_history_update_simple)
        core_api.bind_to_history_update_deep(self._handle_history_update_deep)
        core_api.bind_to_history_update_text(self._handle_history_update_text)
        core_api.bind_to_history_remove(self._handle_history_remove)
        core_api.bind_to_history(self._handle_history)

    def _init_accelerators(self):
        config = coreaux_api.get_interface_configuration("wxgui")(
                            "ContextualShortcuts")("LeftNotebook")("Database")
        self.accelerators.update({
            config["expand"]: lambda event: self.expand_focused_item(),
            config["collapse"]: lambda event: self.collapse_focused_item(),
            config["select"]: lambda event:
                                        self.add_focused_item_to_selection(),
            config["unselect"]: lambda event:
                                    self.remove_focused_item_from_selection(),
            config["undo"]: lambda event: self.undo(),
            config["redo"]: lambda event: self.redo(),
            config["create_sibling"]: lambda event: self.create_sibling(),
            config["create_child"]: lambda event: self.create_child(),
            config["move_up"]: lambda event: self.move_item_up(),
            config["move_down"]: lambda event: self.move_item_down(),
            config["move_to_parent"]: lambda event: self.move_item_to_parent(),
            config["edit"]: lambda event: self.edit_item(),
            config["delete"]: lambda event: self.delete_selected_items(),
        })
        wx.GetApp().root.accmanager.create_manager(self.treec,
                                                            self.accelerators)

    def install_additional_accelerators(self, accelsconf):
        self.accelerators.update(accelsconf)

    def _handle_insert_item(self, kwargs):
        if kwargs['filename'] == self.filename:
            parent = self.get_tree_item_safe(kwargs['parent'])
            self._insert_item(parent, kwargs['id_'], kwargs['text'])

    def _handle_update_item_text(self, kwargs):
        # Don't update an item label only when editing the text area, as there
        # may be other plugins that edit an item's text (e.g links)
        # kwargs['text'] could be None if the query updated the position of the
        # item and not its text
        if kwargs['filename'] == self.filename:
            id_ = kwargs['id_']
            self._set_item_label(id_, kwargs['text'])
            self.update_tree_item(id_)

    def _handle_deleting_item(self, kwargs):
        if kwargs['filename'] == self.filename:
            self._remove_item(kwargs['parent'], kwargs['id_'])

    def _handle_deleted_item(self, kwargs):
        if kwargs['filename'] == self.filename:
            self._remove_item_data(kwargs['id_'])

    def _handle_history_insert(self, kwargs):
        if kwargs['filename'] == self.filename:
            self._init_item_data(kwargs["id_"], kwargs["text"])
            self._request_tree_reset()

    def _handle_history_update_simple(self, kwargs):
        if kwargs['filename'] == self.filename:
            self._request_tree_reset()

    def _handle_history_update_deep(self, kwargs):
        if kwargs['filename'] == self.filename:
            self._request_tree_reset()

    def _handle_history_update_text(self, kwargs):
        if kwargs['filename'] == self.filename:
            id_ = kwargs['id_']
            self._set_item_label(id_, kwargs['text'])
            self.request_item_refresh(id_)

    def _handle_history_remove(self, kwargs):
        if kwargs['filename'] == self.filename:
            self._remove_item_data(kwargs['id_'])
            self._request_tree_reset()

    def _request_tree_reset(self):
        self.history_tree_reset_request = True

    def request_item_refresh(self, id_):
        self.history_item_update_requests.append(id_)

    def _handle_history(self, kwargs):
        # Yes, this is a very aggressive way of handling history actions, this
        # is redrawing the whole tree whenever an item is
        # inserted/moved/deleted, however trying to handle each case separately
        # is very complicated and thus causes numerous bugs, because each query
        # in the history group can leave the database in an unstable state
        # (e.g. the queries that update the previous id to the next/previous
        # items when moving an item)
        # It should be quite efficient anyway because self.data is not
        # recalculated except for the items that explicitly requested it, and
        # only the root items and their children are re-added, the rest of the
        # items will be re-added on request (when their parents are expanded
        # again)
        if kwargs['filename'] == self.filename:
            if self.history_tree_reset_request:
                self.dvmodel.Cleared()

                for id_ in core_api.get_root_items(self.filename):
                    item = self.get_tree_item(id_)
                    # For some reason ItemDeleted must be called too first...
                    self.dvmodel.ItemDeleted(self._get_root(), item)
                    self.dvmodel.ItemAdded(self._get_root(), item)
                    self._reset_children(id_, item)

            for id_ in self.history_item_update_requests:
                # id_ may have been deleted by an action in the history group
                if core_api.is_item(self.filename, id_):
                    self.update_tree_item(id_)

            del self.history_item_update_requests[:]
            self.history_tree_reset_request = False

    @classmethod
    def open(cls, filename):
        global dbs
        dbs[filename] = cls(filename)

        dbs[filename]._post_init()

    def save(self):
        if core_api.check_pending_changes(self.filename):
            try:
                core_api.save_database(self.filename)
            except OutsplineError as err:
                databases.warn_aborted_save(err)
            else:
                self.dbhistory.refresh()

    def undo(self, no_confirm=False):
        if core_api.block_databases():
            read = core_api.preview_undo_tree(self.filename)

            if read:
                for id_ in read:
                    item = editor.Editor.make_tabid(self.filename, id_)

                    if item in editor.tabs and not editor.tabs[item].close(
                                    ask='quiet' if no_confirm else 'discard'):
                        break
                else:
                    core_api.undo_tree(self.filename)
                    self.dbhistory.refresh()
                    undo_tree_event.signal(filename=self.filename)

            core_api.release_databases()

    def redo(self, no_confirm=False):
        if core_api.block_databases():
            read = core_api.preview_redo_tree(self.filename)

            if read:
                for id_ in read:
                    item = editor.Editor.make_tabid(self.filename, id_)

                    if item in editor.tabs and not editor.tabs[item].close(
                                    ask='quiet' if no_confirm else 'discard'):
                        break
                else:
                    core_api.redo_tree(self.filename)
                    self.dbhistory.refresh()
                    redo_tree_event.signal(filename=self.filename)

            core_api.release_databases()

    def create_sibling(self):
        if core_api.block_databases():
            # Do not use none=False in order to allow the creation of the
            # first item
            selection = self.get_selections(many=False)

            # If multiple items are selected, selection will be False
            if selection is not False:
                text = 'New item'

                if len(selection) > 0:
                    previd = self.get_item_id(selection[0])
                    parid = core_api.get_item_parent(self.filename, previd)

                    id_ = core_api.create_sibling(filename=self.filename,
                                parent=parid, previous=previd,
                                text=text, description='Insert item')
                else:
                    id_ = core_api.create_child(filename=self.filename,
                                                parent=0, text=text,
                                                description='Insert item')

                self.select_item(id_)
                self.dbhistory.refresh()

            core_api.release_databases()

    def create_child(self):
        if core_api.block_databases():
            selection = self.get_selections(none=False, many=False)

            if selection:
                pid = self.get_item_id(selection[0])

                id_ = core_api.create_child(filename=self.filename,
                                            parent=pid, text='New item',
                                            description='Insert sub-item')

                self.select_item(id_)
                self.dbhistory.refresh()

            core_api.release_databases()

    def _insert_item(self, parent, id_, text):
        self._init_item_data(id_, text)
        self.dvmodel.ItemAdded(parent, self.get_tree_item(id_))

    def _init_item_data(self, id_, text):
        label = self._make_item_label(text)
        multiline_bits, multiline_mask = \
                    self.base_properties.get_item_multiline_state(text, label)
        properties = self._compute_property_bits(0, multiline_bits,
                                                                multiline_mask)
        self.data[id_] = Item(id_, label, properties)

    def get_selections(self, none=True, many=True, descendants=None):
        selection = self.treec.GetSelections()

        if (not none and len(selection) == 0) or (not many and
                                                        len(selection) > 1):
            return False
        elif descendants == True:
            for item in selection:
                id_ = self.get_item_id(item)

                for descid in core_api.get_item_descendants(self.filename,
                                                                        id_):
                    self.treec.Select(self.get_tree_item(descid))

            return self.treec.GetSelections()
        else:
            return selection

    def move_item_up(self):
        if core_api.block_databases():
            selection = self.get_selections(none=False, many=False)

            if selection:
                item = selection[0]
                id_ = self.get_item_id(item)

                if core_api.move_item_up(self.filename, id_,
                                            description='Move item up'):
                    self._move_item(id_, item)
                    self.select_item(id_)
                    self.dbhistory.refresh()

            core_api.release_databases()

    def move_item_down(self):
        if core_api.block_databases():
            selection = self.get_selections(none=False, many=False)

            if selection:
                item = selection[0]
                id_ = self.get_item_id(item)

                if core_api.move_item_down(self.filename, id_,
                                            description='Move item down'):
                    self._move_item(id_, item)
                    self.select_item(id_)
                    self.dbhistory.refresh()

            core_api.release_databases()

    def _move_item(self, id_, item):
        pid = core_api.get_item_parent(self.filename, id_)
        parent = self.get_tree_item_safe(pid)

        self.dvmodel.ItemDeleted(parent, item)
        self.dvmodel.ItemAdded(parent, item)
        self._reset_children(id_, item)

    def move_item_to_parent(self):
        if core_api.block_databases():
            selection = self.get_selections(none=False, many=False)

            if selection:
                item = selection[0]
                id_ = self.get_item_id(item)
                oldpid = core_api.get_item_parent(self.filename, id_)

                if core_api.move_item_to_parent(self.filename, id_,
                                        description='Move item to parent'):

                    newpid = core_api.get_item_parent(self.filename, id_)

                    # oldpid cannot be 0 here because
                    # core_api.move_item_to_parent succeded, which means that
                    # it wasn't the root item
                    oldparent = self.get_tree_item(oldpid)
                    newparent = self.get_tree_item_safe(newpid)

                    self.dvmodel.ItemDeleted(oldparent, item)
                    self.dvmodel.ItemAdded(newparent, item)
                    self._reset_children(id_, item)
                    self._refresh_item_arrow(newparent, oldpid, oldparent)
                    self.select_item(id_)
                    self.dbhistory.refresh()

            core_api.release_databases()

    def _reset_children(self, id_, item):
        childids = core_api.get_item_children(self.filename, id_)

        for childid in childids:
            child = self.get_tree_item(childid)
            self.dvmodel.ItemAdded(item, child)
            # There's no need to make this recursive and re-add all the
            #  descendants immediately: they'll be re-added on request (when
            #  their parents will be expanded again)
            # Making this recursive would be exaggerately slow
            #self._reset_children(childid, child)

    def edit_item(self):
        selection = self.get_selections(none=False)

        if selection:
            for sel in selection:
                id_ = self.get_item_id(sel)
                editor.Editor.open(self.filename, id_)

    def delete_selected_items(self, no_confirm=False):
        if core_api.block_databases():
            selection = self.get_selections(none=False, descendants=True)

            if selection:
                items = []

                for item in selection:
                    id_ = self.get_item_id(item)
                    tab = editor.Editor.make_tabid(self.filename, id_)

                    if tab in editor.tabs and not editor.tabs[tab].close(
                                    'quiet' if no_confirm else 'discard'):
                        core_api.release_databases()
                        return False

                    items.append(id_)

                self.delete_items(items,
                        description='Delete {} items'.format(len(items)))
                self.dbhistory.refresh()
                delete_items_event.signal()

            core_api.release_databases()

    def delete_items(self, ids, description="Delete items"):
        group = core_api.get_next_history_group(self.filename)
        roots = core_api.find_independent_items(self.filename, ids)

        for root in roots:
            rootpid = core_api.get_item_parent(self.filename, root)

            core_api.delete_subtree(self.filename, root, group=group,
                                                    description=description)

            if rootpid > 0:
                rootpid2 = core_api.get_item_parent(self.filename, rootpid)
                rootparent2 = self.get_tree_item_safe(rootpid2)

                self._refresh_item_arrow(rootparent2, rootpid,
                                                self.get_tree_item(rootpid))

    def _refresh_item_arrow(self, parent, id_, item):
        if not core_api.has_item_children(self.filename, id_):
            # This seems to be the only way to hide the arrow next to a parent
            # that has just lost all of its children
            self.dvmodel.ItemDeleted(parent, item)
            self.dvmodel.ItemAdded(parent, item)

    def _remove_item(self, pid, id_):
        item = self.get_tree_item(id_)
        parent = self.get_tree_item_safe(pid)
        self.dvmodel.ItemDeleted(parent, item)

    def _remove_item_data(self, id_):
        del self.data[id_]

    def close(self):
        global dbs
        del dbs[self.filename]

    def show_logs(self):
        self.SplitHorizontally(self.treec, self.logspanel.get_panel())
        height = self.GetSize().GetHeight()
        self.SetSashGravity(self.sash_gravity)
        self.SetSashPosition(height // self.sash_position * -1)

    def hide_logs(self):
        self.Unsplit(self.logspanel.get_panel())

    def get_filename(self):
        return self.filename

    def _get_root(self):
        return dv.NullDataViewItem

    def get_item_id(self, item):
        return self.dvmodel.ItemToObject(item).get_id()

    def get_tree_item(self, id_):
        return self.dvmodel.ObjectToItem(self.data[id_])

    def get_tree_item_safe(self, id_):
        if id_ > 0:
            return self.get_tree_item(id_)
        else:
            return self._get_root()

    @staticmethod
    def _make_item_label(text):
        return text.partition('\n')[0]

    def get_item_label(self, id_):
        return self.data[id_].get_label()

    def get_item_properties(self, id_):
        return self.properties.get(self.data[id_].get_properties())

    def _set_item_label(self, id_, text):
        label = self._make_item_label(text)
        self.data[id_].set_label(label)
        multiline_bits, multiline_mask = \
                    self.base_properties.get_item_multiline_state(text, label)
        self.update_item_properties(id_, multiline_bits, multiline_mask)

    @staticmethod
    def _compute_property_bits(old_property_bits, new_property_bits,
                                                                property_mask):
        return (old_property_bits & ~property_mask) | new_property_bits

    def update_item_properties(self, id_, property_bits, property_mask):
        self.data[id_].set_properties(self._compute_property_bits(
                self.data[id_].get_properties(), property_bits, property_mask))

    def update_tree_item(self, id_):
        self.dvmodel.ItemChanged(self.get_tree_item(id_))

    def add_property(self, *args, **kwargs):
        return self.properties.add(*args, **kwargs)

    def get_logs_panel(self):
        return self.logspanel

    def select_item(self, id_):
        self.treec.UnselectAll()
        self.treec.Select(self.get_tree_item(id_))

    def unselect_all_items(self):
        self.treec.UnselectAll()

    def add_item_to_selection(self, id_):
        self.treec.Select(self.get_tree_item(id_))

    def add_focused_item_to_selection(self):
        self.treec.Select(self.treec.GetCurrentItem())

    def remove_item_from_selection(self, id_):
        self.treec.Unselect(self.get_tree_item(id_))

    def remove_focused_item_from_selection(self):
        self.treec.Unselect(self.treec.GetCurrentItem())

    def expand_focused_item(self):
        self.treec.Expand(self.treec.GetCurrentItem())

    def collapse_focused_item(self):
        self.treec.Collapse(self.treec.GetCurrentItem())

    def expand_item_ancestors(self, id_):
        # Not all items in the tree are created immediately: only the visible
        #  ones and their direct children are, but all the others are only
        #  added on request, i.e. when their grandparent is expanded. This
        #  means that if some plugins (e.g. wxdevelopment) try to create a
        #  child of an item whose parent hasn't been expanded yet, an exception
        #  will be raised, complaining that the parent item doesn't exist in
        #  the tree. Calling this method before adding an item programmatically
        #  ensures that this exception won't be raised.
        #  For example, take the following database that was saved during a
        #  previous Outspline session and has *never* been expanded before,
        #  during this session:
        #  > A
        #    > B
        #      * C
        #  Now, if wxdevelopment's populate_tree tried to create a child of C,
        #  it would crash, because C has never been added to the tree, since
        # the children of B have  never been requested
        self.treec.ExpandAncestors(self.get_tree_item(id_))

    def focus_database(self):
        self.treec.SetFocus()

    def _popup_item_menu(self, event):
        self.cmenu.update_items()
        popup_context_menu_event.signal(filename=self.filename)
        self.treec.PopupMenu(self.cmenu, event.GetPosition())

    def get_tab_context_menu(self):
        self.ctabmenu.update()
        return self.ctabmenu


class DBProperties(object):
    def __init__(self, properties):
        config = coreaux_api.get_interface_configuration('wxgui')('TreeIcons')
        multichar = config['symbol']

        if multichar != '':
            bits_to_color = {
                1: wx.Colour(),
            }
            bits_to_color[1].SetFromString(config['color'])

            self.multiline_shift, self.multiline_mask = properties.add(1,
                                                    multichar, bits_to_color)

    def get_item_multiline_state(self, text, label):
        if text != label:
            bits = 1 << self.multiline_shift
        else:
            bits = 0

        return (bits, self.multiline_mask)


class Properties(object):
    def __init__(self, widget):
        self.widget = widget

        self.bitsn = 0
        self.data = []
        self.bits_to_chars = {}

    def add(self, bitsn, character, bits_to_color):
        shift = self.bitsn
        mask = int('1' * bitsn, 2) << shift
        self.bitsn += bitsn
        shifted_bits_to_colors = {}

        for bits in bits_to_color:
            shifted_bits_to_colors[bits << shift] = bits_to_color[bits]

        self.data.append((mask, character, shifted_bits_to_colors))

        return (shift, mask)

    def post_init(self):
        # char_data is empty if no properties have been added
        if len(self.data) < 1:
            self.get = self._get_dummy
        else:
            self.get = self._get_real

    def get(self, bits):
        # This method is re-assigned dynamically
        pass

    def _get_real(self, bits):
        try:
            return self.bits_to_chars[bits]
        except KeyError:
            teststr, strdata = self._compute_data(bits)
            self.bits_to_chars[bits] = teststr, strdata
            return teststr, strdata

    def _get_dummy(self, bits):
        # Used if no properties have been added
        return ("", [])

    def _compute_data(self, item_bits):
        teststr = ""
        strdata = []

        for property_bits, character, bits_to_colors in self.data:
            bits = (property_bits & item_bits)

            try:
                color = bits_to_colors[bits]
            except KeyError:
                pass
            else:
                teststr += character
                strdata.append((character, color))

        return (teststr, strdata)


class ContextMenu(wx.Menu):
    def __init__(self, parent):
        wx.Menu.__init__(self)

        self.sibling_label_1 = "Create &item"
        self.sibling_label_2 = "Create s&ibling"

        self.parent = parent

        self.sibling = wx.MenuItem(self, wx.GetApp().menu.database.ID_SIBLING,
                                                        self.sibling_label_1)
        self.child = wx.MenuItem(self, wx.GetApp().menu.database.ID_CHILD,
                                                            "Create c&hild")
        self.moveup = wx.MenuItem(self, wx.GetApp().menu.database.ID_MOVE_UP,
                                                            "&Move item up")
        self.movedn = wx.MenuItem(self, wx.GetApp().menu.database.ID_MOVE_DOWN,
                                                            "Mo&ve item down")
        self.movept = wx.MenuItem(self,
                                    wx.GetApp().menu.database.ID_MOVE_PARENT,
                                    "M&ove item to parent")
        self.edit = wx.MenuItem(self, wx.GetApp().menu.database.ID_EDIT,
                                                                "&Edit item")
        self.delete = wx.MenuItem(self, wx.GetApp().menu.database.ID_DELETE,
                                                            "&Delete items")

        self.sibling.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@new'))
        self.child.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@new'))
        self.moveup.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@up'))
        self.movedn.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@down'))
        self.movept.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@left'))
        self.edit.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@edit'))
        self.delete.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@delete'))

        self.AppendItem(self.sibling)
        self.AppendItem(self.child)
        self.AppendSeparator()
        self.AppendItem(self.moveup)
        self.AppendItem(self.movedn)
        self.AppendItem(self.movept)
        self.AppendSeparator()
        self.AppendItem(self.edit)
        self.AppendSeparator()
        self.AppendItem(self.delete)

    def _reset_items(self):
        self.sibling.Enable(False)
        self.child.Enable(False)
        self.moveup.Enable(False)
        self.movedn.Enable(False)
        self.movept.Enable(False)
        self.edit.Enable(False)
        self.delete.Enable(False)
        self.sibling.SetItemLabel(self.sibling_label_1)

        reset_context_menu_event.signal(filename=self.parent.filename)

    def update_items(self):
        self._reset_items()

        sel = self.parent.get_selections()

        if len(sel) == 1:
            self.sibling.Enable()
            self.sibling.SetItemLabel(self.sibling_label_2)
            self.child.Enable()

            id_ = self.parent.get_item_id(sel[0])

            if core_api.get_item_previous(self.parent.filename, id_):
                self.moveup.Enable()

            if core_api.get_item_next(self.parent.filename, id_):
                self.movedn.Enable()

            if not core_api.is_item_root(self.parent.filename, id_):
                self.movept.Enable()

            self.edit.Enable()
            self.delete.Enable()

        elif len(sel) > 1:
            self.edit.Enable()
            self.delete.Enable()

        else:
            self.sibling.Enable()


class TabContextMenu(wx.Menu):
    def __init__(self, filename):
        wx.Menu.__init__(self)
        self.filename = filename

        self.undo = wx.MenuItem(self, wx.GetApp().menu.database.ID_UNDO,
                                                                       "&Undo")
        self.redo = wx.MenuItem(self, wx.GetApp().menu.database.ID_REDO,
                                                                       "&Redo")
        self.save = wx.MenuItem(self, wx.GetApp().menu.file.ID_SAVE, "&Save")
        self.saveas = wx.MenuItem(self, wx.GetApp().menu.file.ID_SAVE_AS,
                                                                 "Sav&e as...")
        self.backup = wx.MenuItem(self, wx.GetApp().menu.file.ID_BACKUP,
                                                             "Save &backup...")
        self.properties = wx.MenuItem(self,
                            wx.GetApp().menu.file.ID_PROPERTIES, "&Properties")
        self.close = wx.MenuItem(self, wx.GetApp().menu.file.ID_CLOSE_DB,
                                                                      "&Close")

        self.undo.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@undo'))
        self.redo.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@redo'))
        self.save.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@save'))
        self.saveas.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@saveas'))
        self.backup.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@saveas'))
        self.properties.SetBitmap(wx.GetApp().artprovider.get_menu_icon(
                                                                '@properties'))
        self.close.SetBitmap(wx.GetApp().artprovider.get_menu_icon('@close'))

        self.AppendItem(self.undo)
        self.AppendItem(self.redo)
        self.AppendSeparator()
        self.AppendItem(self.save)
        self.AppendItem(self.saveas)
        self.AppendItem(self.backup)
        self.AppendSeparator()
        self.AppendItem(self.properties)
        self.AppendSeparator()
        self.AppendItem(self.close)

    def update(self):
        if core_api.preview_undo_tree(self.filename):
            self.undo.Enable()
        else:
            self.undo.Enable(False)

        if core_api.preview_redo_tree(self.filename):
            self.redo.Enable()
        else:
            self.redo.Enable(False)

        if core_api.check_pending_changes(self.filename):
            self.save.Enable()
        else:
            self.save.Enable(False)
