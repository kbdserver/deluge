# -*- coding: utf-8 -*-
#
# Copyright (C) 2008 Andrew Resch <andrewresch@gmail.com>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

from __future__ import unicode_literals

import logging
import os.path

from gi.repository import Gtk

import deluge.component as component
from deluge.ui.client import client
from deluge.common import fdate, is_url, resource_filename

from .common import load_pickled_state_file, save_pickled_state_file
from .torrentdetails import Tab

log = logging.getLogger(__name__)


def trackers_tiers_from_text(text_str = ''):
    """Create a list of trackers from text.

    Any duplicate trackers are removed.
    Args:
        text_input (str): A block of text with tracker separated by newlines.
    Returns:
        list: The list of trackers.
    Notes:
        Trackers should be separated by newlines and empty line denotes start of new tier.
    """

    trackers = {}
    tier = 0

    lines = text_str.strip().split('\n')
    for line in lines:
        if not line:
            tier += 1
            continue
        line = line.replace('\\', '/')  # Fix any mistyped urls.
        if is_url(line) and line not in trackers:
            trackers[line] = tier

    return trackers


class TrackersTab(Tab):
    def __init__(self):
        super(TrackersTab, self).__init__('Trackers', 'trackers_tab', 'trackers_tab_label')

        self.builder = Gtk.Builder()
        # add tracker dialog
        self.builder.add_from_file(resource_filename(
            __package__, os.path.join('glade', 'edit_trackers.add.ui'),
        ))

        component.get('MainWindow').connect_signals(self)

        self.listview = self.main_builder.get_object('trackers_listview')
        self.listview.connect('button-press-event', self._on_button_press_event)

        # is_active, tier, icon, tracker_url, seeds, peers, status, next_announce, tracker_message
        self.liststore = Gtk.ListStore(str, int, str, int, int, str, str, str)
        self.liststore.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        # key is url, item is row iter
        self.trackers = {}
        self.trackers_set = []

        self.tracker_status = self.main_builder.get_object('tracker_status_label')

        # is_active column
        column = Gtk.TreeViewColumn(_(' '))
        render = Gtk.CellRendererText()
        column.pack_start(render, False)
        column.add_attribute(render, 'text', 0)
        column.set_sort_column_id(0)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_expand(False)
        column.set_min_width(20)
        column.set_reorderable(True)
        self.listview.append_column(column)

        # tier column
        column = Gtk.TreeViewColumn(_('Tier'))
        render = Gtk.CellRendererText()
        column.pack_start(render, False)
        column.add_attribute(render, 'text', 1)
        column.set_sort_column_id(1)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_expand(False)
        column.set_min_width(20)
        column.set_reorderable(True)
        self.listview.append_column(column)

        # tracker_url column
        column = Gtk.TreeViewColumn(_('Tracker'))
        render = Gtk.CellRendererText()
        render.set_property('editable', True)
        render.connect('edited', self._on_tracker_edited)
        render.connect('editing-started', self._on_tracker_editing_start)
        render.connect('editing-canceled', self._on_tracker_editing_canceled)
        column.pack_start(render, True)
        column.add_attribute(render, 'text', 2)
        column.set_sort_column_id(2)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_expand(False)
        column.set_min_width(200)
        column.set_reorderable(True)
        self.listview.append_column(column)

        # seeds column
        column = Gtk.TreeViewColumn(_('Seeds'))
        render = Gtk.CellRendererText()
        column.pack_start(render, False)
        column.add_attribute(render, 'text', 3)
        column.set_sort_column_id(3)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_expand(False)
        column.set_min_width(20)
        column.set_reorderable(True)
        self.listview.append_column(column)

        # peers column
        column = Gtk.TreeViewColumn(_('Peers'))
        render = Gtk.CellRendererText()
        column.pack_start(render, False)
        column.add_attribute(render, 'text', 4)
        column.set_sort_column_id(4)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_expand(False)
        column.set_min_width(20)
        column.set_reorderable(True)
        self.listview.append_column(column)

        # status column
        column = Gtk.TreeViewColumn(_('Status'))
        render = Gtk.CellRendererText()
        column.pack_start(render, False)
        column.add_attribute(render, 'text', 5)
        column.set_sort_column_id(5)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_expand(False)
        column.set_min_width(20)
        column.set_reorderable(True)
        self.listview.append_column(column)

        # next_announce column
        column = Gtk.TreeViewColumn(_('Next Announce'))
        render = Gtk.CellRendererText()
        column.pack_start(render, False)
        column.add_attribute(render, 'text', 6)
        column.set_sort_column_id(6)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_expand(False)
        column.set_min_width(20)
        column.set_reorderable(True)
        self.listview.append_column(column)

        # tracker_message column
        column = Gtk.TreeViewColumn(_('Message'))
        render = Gtk.CellRendererText()
        column.pack_start(render, False)
        column.add_attribute(render, 'text', 7)
        column.set_sort_column_id(7)
        column.set_clickable(True)
        column.set_resizable(True)
        column.set_expand(False)
        column.set_min_width(20)
        column.set_reorderable(True)
        self.listview.append_column(column)

        self.listview.set_model(self.liststore)

        self.hide_trackers_bar = False
        self.load_state()

        self.trackers_menu = self.main_builder.get_object('menu_trackers_tab')
        self.main_builder.get_object('menuitem_hide_buttons').set_active(self.hide_trackers_bar)

        if self.hide_trackers_bar:
            self.main_builder.get_object('trackers_bar').hide()

        self.torrent_id = None
        self.editing_start = False

    def save_state(self):
        # Get the current sort order of the view
        column_id, sort_order = self.liststore.get_sort_column_id()

        # Setup state dict
        state = {
            'columns': {},
            'sort_id': column_id,
            'sort_order': int(sort_order) if sort_order else None,
            'hide_trackers_bar': self.hide_trackers_bar,
        }

        for index, column in enumerate(self.listview.get_columns()):
            state['columns'][column.get_title()] = {
                'position': index,
                'width': column.get_width(),
            }
        save_pickled_state_file('trackers_tab.state', state)

    def load_state(self):
        state = load_pickled_state_file('trackers_tab.state')

        if state is None:
            return

        if len(state['columns']) != len(self.listview.get_columns()):
            log.warning('trackers_tab.state is not compatible! rejecting..')
            return

        if state['sort_id'] and state['sort_order'] is not None:
            self.liststore.set_sort_column_id(state['sort_id'], state['sort_order'])

        if state['hide_trackers_bar'] is not None:
            self.hide_trackers_bar = state['hide_trackers_bar']

        column = None
        for (index, column) in enumerate(self.listview.get_columns()):
            cname = column.get_title()
            if cname in state['columns']:
                cstate = state['columns'][cname]
                column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
                column.set_fixed_width(cstate['width'] if cstate['width'] > 0 else 10)
                if state['sort_id'] == index and state['sort_order'] is not None:
                    column.set_sort_indicator(True)
                    column.set_sort_order(state['sort_order'])
                if cstate['position'] != index:
                    # Column is in wrong position
                    if cstate['position'] == 0:
                        self.listview.move_column_after(column, None)
                    elif self.listview.get_columns()[cstate['position'] - 1].get_title() != cname:
                        self.listview.move_column_after(column, self.listview.get_columns()[cstate['position'] - 1])
        # Bugfix: Last column needs autosizing set to stop h_scrollbar appearing
        column.set_fixed_width(-1)
        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)

    def _on_button_press_event(self, widget, event):
        """This is a callback for showing the right-click context menu."""
        log.debug('on_button_press_event')
        # We only care about right-clicks
        if event.button == 3 and event.window == self.listview.get_bin_window():
            x, y = event.get_coords()
            cursor_path = self.listview.get_path_at_pos(int(x), int(y))

            if cursor_path:
                paths = self.listview.get_selection().get_selected_rows()[1]
                if cursor_path[0] not in paths:
                    row = self.liststore.get_iter(cursor_path[0])
                    self.listview.get_selection().unselect_all()
                    self.listview.get_selection().select_iter(row)
                    self.main_builder.get_object('menuitem_edit_tracker').set_sensitive(True)
                    self.main_builder.get_object('menuitem_remove_trackers').set_sensitive(True)
                    self.main_builder.get_object('menuitem_up').set_sensitive(True)
                    self.main_builder.get_object('menuitem_down').set_sensitive(True)
            else:
                self.listview.get_selection().unselect_all()
                self.main_builder.get_object('menuitem_edit_tracker').set_sensitive(False)
                self.main_builder.get_object('menuitem_remove_trackers').set_sensitive(False)
                self.main_builder.get_object('menuitem_up').set_sensitive(False)
                self.main_builder.get_object('menuitem_down').set_sensitive(False)

            self.trackers_menu.popup(None, None, None, None, event.button, event.time)
            return True

    def update(self):
        if self.editing_start:
            return

        # Get the first selected torrent
        torrent_id = component.get('TorrentView').get_selected_torrents()

        # Only use the first torrent in the list or return if None selected
        if len(torrent_id) != 0:
            torrent_id = torrent_id[0]
        else:
            # No torrent is selected in the torrentview
            self.liststore.clear()
            return

        if torrent_id != self.torrent_id:
            # We only want to do this if the torrent_id has changed
            self.liststore.clear()
            self.trackers = {}
            self.torrent_id = torrent_id

        component.get('SessionProxy').get_torrent_status(self.torrent_id, ['trackers', 'tracker']) \
            .addCallback(self._on_set_trackers)

    def _on_set_trackers(self, status):
        new_tracker = set()

        for tracker in status['trackers']:
            new_tracker.add(tracker['url'])
            if tracker['updating']:
                tracker_status = 'updating'
            elif tracker['verified']:
                tracker_status = 'active'
            elif tracker['last_error']['value'] != 0:
                tracker_status = 'not active'
            else:
                tracker_status = 'reserved'
            if 'message' in tracker != '':
                message = tracker['message'].lower()
            else:
                message = ''

            if tracker['url'] in self.trackers:
                # We already have this tracker in our list, so lets just update it
                row = self.trackers[tracker['url']]
                if not self.liststore.iter_is_valid(row):
                    # This iter is invalid, delete it and continue to next iteration
                    del self.trackers[tracker['url']]
                    continue
                values = self.liststore.get(row, 0, 1, 2, 3, 4, 5, 6, 7)
                if tracker['url'] == status['tracker']:
                    self.liststore.set_value(row, 0, '>')
                else:
                    self.liststore.set_value(row, 0, '')
                if tracker['tier'] != values[1]:
                    self.liststore.set_value(row, 1, tracker['tier'])
                if tracker['url'] != values[2]:
                    self.liststore.set_value(row, 2, tracker['url'])
                if tracker['scrape_complete'] != values[3]:
                    self.liststore.set_value(row, 3,
                                             tracker['scrape_complete']
                                             if tracker['scrape_complete'] > -1
                                             else None)
                if tracker['scrape_incomplete'] != values[4]:
                    self.liststore.set_value(row, 4,
                                             tracker['scrape_incomplete']
                                             if tracker['scrape_incomplete'] > -1
                                             else None)
                if tracker_status != values[5]:
                    self.liststore.set_value(row, 5, tracker_status)
                if (fdate(tracker['next_announce']).split()[1] \
                        if tracker['next_announce'] and tracker['next_announce'] > 0 else None) != values[6]:
                    self.liststore.set_value(row, 6,
                                             fdate(tracker['next_announce']).split()[1]
                                             if tracker['next_announce'] > 0 else None)
                if message != values[7]:
                    self.liststore.set_value(row, 7, message)
            else:
                # Tracker is not in list so we need to add it
                row = self.liststore.append(['>' if tracker['url'] == status['tracker'] else '',
                                            tracker['tier'],
                                            tracker['url'],
                                            tracker['scrape_complete']
                                             if tracker['scrape_complete'] > -1 else None,
                                            tracker['scrape_incomplete']
                                             if tracker['scrape_incomplete'] > -1 else None,
                                            tracker_status,
                                            fdate(tracker['next_announce']).split()[1]
                                             if tracker['next_announce'] and tracker['next_announce'] > 0 else None,
                                             message,
                                             ])

                self.trackers[tracker['url']] = row

    def clear(self):
        self.liststore.clear()

    def _on_tracker_editing_start(self, renderer, editable, path):
        self.editing_start = True
        return

    def _on_tracker_editing_canceled(self, renderer):
        self.editing_start = False
        return

    def _on_tracker_edited(self, renderer, path, new_url):
        i = self.liststore.get_iter(path)
        del self.trackers[self.liststore.get_value(i, 2)]
        self.liststore.set_value(i, 2, new_url)
        self.trackers[new_url] = i
        self.set_trackers()
        self.editing_start = False
        return

    def get_selected(self):
        """Returns the selected trackers iters"""
        selected = []
        paths = self.listview.get_selection().get_selected_rows()[1]
        for path in paths:
            selected.append(self.liststore.get_iter(path))
        return selected

    def on_button_add_clicked(self, widget):
        log.debug('on_button_add_clicked')
        # Show the add tracker dialog
        dialog = self.builder.get_object('add_tracker_dialog')
        textview = self.builder.get_object('textview_trackers')

        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.set_transient_for(component.get('MainWindow').window)
        textview.grab_focus()

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:

            # Create a list of trackers from the textview widget
            textview_buf = self.builder.get_object(
                'textview_trackers').get_buffer()
            trackers_text = textview_buf.get_text(
                *textview_buf.get_bounds(), include_hidden_chars=False)

            for tracker in trackers_tiers_from_text(trackers_text):
                # Figure out what tier number to use.. it's going to be the highest+1
                # Also check for duplicates
                # Check if there are any entries
                duplicate = False
                highest_tier = -1
                for row in self.liststore:
                    tier = row[1]
                    if tier > highest_tier:
                        highest_tier = tier
                    if tracker == row[2]:
                        duplicate = True
                        break

                # If not a duplicate, then add it to the list
                if not duplicate:
                    # Add the tracker to the list
                    row = self.liststore.append(['', highest_tier + 1, tracker, 0, 0, '', '', ''])
                    self.trackers[tracker] = row
                    self.set_trackers()
            textview_buf.set_text('')

        textview.get_buffer().set_text('')
        dialog.hide()

    def on_button_edit_clicked(self, widget):
        log.debug('on_button_edit_clicked')
        selected = self.get_selected()
        if not selected:
            return
        path = self.liststore.get_path(selected[0])
        for idx in range(0, self.listview.get_n_columns()):
            column = self.listview.get_column(idx)
            if column.get_sort_column_id() == 2:
                self.listview.set_cursor(path, column, True)
                break

    def on_button_remove_clicked(self, widget):
        log.debug('on_button_remove_clicked')
        selected = self.get_selected()
        if not selected:
            return
        for i in selected:
            # Now remove tracker
            self.liststore.remove(i)
        self.set_trackers()

    def on_button_up_clicked(self, widget):
        log.debug('on_button_up_clicked')
        selected = self.get_selected()
        if not selected:
            return
        for i in selected:
            tier = self.liststore.get_value(i, 1)
            if tier <= 0:
                continue
            new_tier = tier - 1
            # Now change the tier for this tracker
            self.liststore.set_value(i, 1, new_tier)
        self.set_trackers()

    def on_button_down_clicked(self, widget):
        log.debug('on_button_down_clicked')
        selected = self.get_selected()
        if not selected:
            return
        for i in selected:
            tier = self.liststore.get_value(i, 1)
            new_tier = tier + 1
            # Now change the tier for this tracker
            self.liststore.set_value(i, 1, new_tier)
        self.set_trackers()

    def on_button_update_clicked(self, widget):
        client.core.force_reannounce([self.torrent_id])

    def on_hide_trackers_bar_toggled(self, widget):
        self.hide_trackers_bar = widget.get_active()
        if self.hide_trackers_bar:
            self.main_builder.get_object('trackers_bar').hide()
        else:
            self.main_builder.get_object('trackers_bar').show()

    def set_trackers(self):
        self.trackers_set = []

        def each(model, path, _iter, data):
            tracker = dict()
            tracker['tier'] = model.get_value(_iter, 1)
            tracker['url'] = model.get_value(_iter, 2)
            self.trackers_set.append(tracker)

        self.liststore.foreach(each, None)
        client.core.set_torrent_trackers(self.torrent_id, self.trackers_set)
