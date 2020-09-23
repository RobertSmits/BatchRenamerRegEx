#
# gtkui.py
#
# Copyright (C) 2011 Nathan Hoad <nathan@getoffmalawn.com>
#
# Basic plugin template created by:
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
# Copyright (C) 2007-2009 Andrew Resch <andrewresch@gmail.com>
# Copyright (C) 2009 Damien Churchill <damoxc@gmail.com>
# Copyright (C) 2010 Pedro Algarvio <pedro@algarvio.me>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#

import re
import os

from gi.repository import Gtk

from deluge.log import LOG as log
from deluge.ui.client import client
from deluge.plugins.pluginbase import Gtk3PluginBase
import deluge.component as component
import deluge.common
from deluge.core.torrent import Torrent

from .common import get_resource

class RenameFiles():
    """Class to wrap up the GUI and all filename processing functions"""

    def __init__(self, tor_id, files):
        self.tor_id = tor_id
        self.files = files

    def run(self):
        """Build the GUI and display it."""
        self.builder = Gtk.Builder.new_from_file(get_resource("rename.ui"))
        self.window = self.builder.get_object("RenameDialog")
        self.window.set_transient_for(component.get("MainWindow").window)
        self.find_field = self.builder.get_object("find_field")
        self.replace_field = self.builder.get_object("replace_field")
        self.ext_toggle = self.builder.get_object("ext")

        dic = {
            "on_ok_clicked": self.ok,
            "on_cancel_clicked": self.cancel,
        }

        self.builder.connect_signals(dic)

        self.build_tree_store()
        self.load_tree()
        treeview = self.builder.get_object("treeview")
        treeview.expand_all()
        self.window.show()

    def enable_row(self, cell, path, model):
        """Enable a row and display the new name"""
        model[path][0] = not model[path][0]

        i = 0

        for child in model[path].iterchildren():
            i += 1
            child[0] = model[path][0]
            self.rename(child)

        if i > 0:
            if model[path][0]:
                model[path][3] = "Can't rename folders. Click to edit me manually!"
            else:
                model[path][3] = ""
        else:
            self.rename(model[path])

    def rename(self, row):
        """Rename according to the user supplied regular expression."""
        if row[0] and row[1]:
            new_name = None
            old_name = row[2]
            ext = ""

            if self.ext_toggle.get_active():
                old_name, ext = os.path.splitext(row[2])

            if len(self.find_field.get_text()) > 0 and len(self.replace_field.get_text()) > 0:
                replace_field = self.replace_field.get_text()
                if replace_field.startswith(r"\U"):
                    new_name = re.sub(self.find_field.get_text(), replace_field[2:], old_name).upper()
                elif replace_field.startswith(r"\L"):
                    new_name = re.sub(self.find_field.get_text(), replace_field[2:], old_name).lower()
                else:
                    new_name = re.sub(self.find_field.get_text(), replace_field, old_name)
            else:
                new_name = old_name

            if self.ext_toggle.get_active():
                new_name += ext

            row[3] = new_name
        elif row[0] and not row[1]:
            row[3] = "Can't rename folders. Click to edit me manually!"
        else:
            row[3] = ""

        for child in row.iterchildren():
            child[0] = row[0]
            self.rename(child)

    def edit_row(self, cell, path, new_text):
        """Set the new name of folders to what was typed."""
        model = self.tree_store
        # this way you can only edit folders, not files.
        if not model[path][1]:
            self.tree_store[path][3] = new_text
            model[path][0] = True

    def build_tree_store(self):
        """Build the tree store to store data."""
        tree_store = Gtk.TreeStore(bool, str, str, str)

        treeview = self.builder.get_object("treeview")
        treeview.set_model(tree_store)

        enable_column = Gtk.TreeViewColumn('Rename')
        index = Gtk.TreeViewColumn('Index')
        old_name = Gtk.TreeViewColumn('Old Name')
        new_name = Gtk.TreeViewColumn('New Name')

        cell = Gtk.CellRendererText()
        cell.set_property('editable', True)
        cell.connect('edited', self.edit_row)

        bool_cell = Gtk.CellRendererToggle()
        bool_cell.set_property('activatable', True)
        bool_cell.connect('toggled', self.enable_row, tree_store)

        enable_column.pack_start(bool_cell, False)
        index.pack_start(cell, False)
        old_name.pack_start(cell, False)
        new_name.pack_start(cell, False)

        enable_column.add_attribute(bool_cell, 'active', 0)
        index.add_attribute(cell, 'text', 1)
        old_name.add_attribute(cell, 'text', 2)
        new_name.add_attribute(cell, 'text', 3)

        treeview.append_column(enable_column)
        treeview.append_column(index)
        treeview.append_column(old_name)
        treeview.append_column(new_name)

        self.tree_store = tree_store

    def load_tree(self):
        """Load the tree store up with the file data."""
        structure = {0: []}
        parents = {}

        files = [(p['path'], p['index']) for p in self.files]

        real_parent = None
        for p, index in files:
            if os.path.basename(p) == p:
                structure[0].append(p)
                self.tree_store.append(None, [False, index, p, ''])

            else:
                parts = p.split('/')
                for i in range(len(parts)):
                    # make sure the depth exists
                    try:
                        structure[i]
                    except KeyError:
                        structure[i] = []

                    # prevents doubles of folders
                    if parts[i] not in structure[i]:
                        structure[i].append(parts[i])

                        try:
                            parent = parents[parts[i - 1]]
                        except KeyError:
                            parent = real_parent

                        # if this, we're adding the actual files, no folders
                        if os.path.basename(p) == parts[i]:
                            self.tree_store.append(parent, [False, str(index), parts[i], ''])
                        # still adding folders -_-
                        else:
                            result = self.tree_store.append(parent, [False, "", parts[i], ''])
                            parents[parts[i]] = result

    def ok(self, arg):
        """Process renaming, as the dialog was closed with OK"""
        self.window.hide()
        self.window.destroy()

        i = 0
        model = self.tree_store

        new_files = []
        try:
            base_name = ""
            while True:
                # only rename selected files
                result = self.get_new_name(model[i], base_name)

                if result:
                    new_files.extend(result)

                i += 1
        except IndexError:
            pass

        log.debug("New file names and indexes:")
        for index, f in new_files:
            log.debug("%d : %s" % (index, f))

        client.batchrenamerregex.rename_torrent_files(self.tor_id, new_files)

    def get_new_name(self, item, base_name):
        """Get the new name from model, and all it's children.

        Keyword arguments:
        item -- The item to retrieve new name info from.
        base_name -- the basename to prepend to new filenames.

        """
        new_files = []
        bad_name = "Can't rename folders. Click to edit me manually!"

        if item[0] and item[1]:
            name = os.path.join(base_name, item[3])
            index = item[1]
            t = [int(index), name]
            new_files.append(t)
        elif not item[1]:
            tmp_base_name = os.path.join(base_name, item[2])
            # if the folder has been renamed to a good name
            if item[3] != bad_name and item[3] != "":
                name = item[3]
                tmp_base_name = os.path.join(base_name, name)

            new_files.extend(self.get_child_names(tmp_base_name, item, bad_name))

        return new_files

    def cancel(self, arg=None):
        """Do nothing, the user doesn't want to rename :("""
        self.window.hide()
        self.window.destroy()

    def get_child_names(self, base_name, parent, bad_name):
        """Get all the new filenames of child elements of the treestore.

        Keyword arguments:
        base_name -- the basename (folder path) to prepend to each filename.
        parent -- the parent to get the children from.
        bad_name -- if this string is found, this item won't be renamed (for folders).

        """
        new_files = []
        for child in parent.iterchildren():
            result = self.get_new_name(child, base_name)

            if result:
                new_files.extend(result)

        return new_files


class GtkUI(Gtk3PluginBase):
    def enable(self):
        self.builder = Gtk.Builder.new_from_file(get_resource("config.ui"))

        # component.get("Preferences").add_page("BatchRenamerRegEx", self.builder.get_object("batch_prefs"))
        
        # add the MenuItem to the context menu.
        img = Gtk.Image.new_from_icon_name(Gtk.STOCK_CONVERT, Gtk.IconSize.MENU)
        self.menu_item = Gtk.ImageMenuItem(_("Rename Files"))
        self.menu_item.set_image(img)
        self.menu_item.connect("activate", self.rename_selected_torrent)
        self.menu_item.show()

        torrentmenu = component.get('MenuBar').torrentmenu
        torrentmenu.append(self.menu_item)

    def disable(self):
        # component.get("Preferences").remove_page("BatchRenamerRegEx")
        component.get("MenuBar").torrentmenu.remove(self.menu_item)

    def rename_selected_torrent(self, arg):
        torrent_id = component.get("TorrentView").get_selected_torrent()
        client.batchrenamerregex.get_torrent_files(torrent_id).addCallback(self.build_dialog)
        log.info(client.batchrenamerregex.get_torrent_files(torrent_id))

    def build_dialog(self, result):
        """Display the dialog using the torrent ID and files."""
        tor_id = result[0]
        files = result[1]
        log.info("Torrent files:")
        log.info(files)
        r = RenameFiles(tor_id, files)
        r.run()
