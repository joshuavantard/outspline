# Organism - A highly modular and extensible outliner.
# Copyright (C) 2011-2013 Dario Giovannetti <dev@dariogiovannetti.net>
#
# This file is part of Organism.
#
# Organism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Organism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Organism.  If not, see <http://www.gnu.org/licenses/>.

import random
import time
import os

import organism.core_api as core_api
import organism.coreaux_api as coreaux_api
from organism.coreaux_api import log
import organism.interfaces.wxgui_api as wxgui_api
wxcopypaste_api = coreaux_api.import_plugin_api('wxcopypaste')
wxscheduler_api = coreaux_api.import_plugin_api('wxscheduler')
wxscheduler_basicrules_api = coreaux_api.import_plugin_api(
                                                       'wxscheduler_basicrules')
wxalarms_api = coreaux_api.import_plugin_api('wxalarms')


def _select_database():
    dbn = core_api.get_databases_count()
    dbid = wxgui_api.get_selected_database_tab_index()
    if dbid > -1:
        choices = [dbid] * 3 + range(dbn)
        wxgui_api.select_database_tab_index(random.choice(choices))
        return True
    else:
        return False


def _select_items(many):
    treedb = wxgui_api.get_active_database()
    filename = treedb.get_filename()
    ids = core_api.get_items_ids(filename)

    if ids:
        w = 0 if many else 1
        modes = (
            (40, 80)[w] * ['select_one'] +
            (10, 0)[w] * ['reselect_many'] +
            (10, 0)[w] * ['select_some'] +
            (10, 0)[w] * ['select_all'] +
            (20, 0)[w] * ['unselect_some'] +
            (10, 20)[w] * ['unselect_all']
        )
        mode = random.choice(modes)

        if mode == 'unselect_some':
            selection = wxgui_api.get_tree_selections(filename)
            if selection:
                sids = [treedb.get_item_id(i) for i in selection]
                remids = random.sample(ids, random.randint(1, len(ids)))
                wxgui_api.simulate_remove_items_from_selection(filename, remids)
        else:
            if mode in ('select_one', 'reselect_many', 'unselect_all'):
                wxgui_api.simulate_unselect_all_items(filename)

            addids = {
                'select_one': (random.choice(ids), ),
                'reselect_many': random.sample(ids, random.randint(
                                           2 if len(ids) > 1 else 1, len(ids))),
                'select_some': random.sample(ids, random.randint(1, len(ids))),
                'select_all': ids,
                'unselect_all': (),
            }

            wxgui_api.simulate_add_items_to_selection(filename, addids[mode])

    return wxgui_api.get_tree_selections(filename)


def _select_editor():
    edids = wxgui_api.get_open_editors_tab_indexes()
    edid = wxgui_api.get_selected_editor_tab_index()
    if edid in edids:
        choices = [edid] * 3 + edids
        wxgui_api.select_editor_tab_index(random.choice(choices))
        return True
    else:
        return False


def create_database():
    testfilesd = coreaux_api.get_plugin_configuration('wxdevelopment')(
                                                                    'TestFiles')
    testfiles = [os.path.expanduser(testfilesd[key]) for key in testfilesd]
    random.shuffle(testfiles)

    while testfiles:
        filename = testfiles.pop()
        if not core_api.is_database_open(filename):
            try:
                os.remove(filename)
            except OSError:
                # filename doesn't exist yet
                pass

            log.debug('Simulate create database')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_create_database(filename)
            break
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def open_database():
    testfilesd = coreaux_api.get_plugin_configuration('wxdevelopment')(
                                                                    'TestFiles')
    testfiles = [os.path.expanduser(testfilesd[key]) for key in testfilesd]
    random.shuffle(testfiles)

    while testfiles:
        filename = testfiles.pop()
        if not core_api.is_database_open(filename) and os.path.isfile(filename):
            log.debug('Simulate open database')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_open_database(filename)
            break
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def save_database():
    if _select_database():
        if random.randint(0, 9) < 9:
            log.debug('Simulate save database')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_save_database()
        else:
            log.debug('Simulate save all databases')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_save_all_databases()
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def close_database():
    if _select_database():
        save = random.randint(0, 5)
        if random.randint(0, 9) < 9:
            log.debug('Simulate' + (' save and ' if save > 0 else ' ') +
                                                               'close database')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            if save > 0:
                wxgui_api.simulate_save_database()
            wxgui_api.simulate_close_database(no_confirm=True)
        else:
            log.debug('Simulate' + (' save and ' if save > 0 else ' ') +
                                                          'close all databases')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            if save > 0:
                wxgui_api.simulate_save_all_databases()
            wxgui_api.simulate_close_all_databases(no_confirm=True)
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def undo_database_history():
    if _select_database():
        log.debug('Simulate undo history')
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        wxgui_api.simulate_undo_tree(no_confirm=True)
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def redo_database_history():
    if _select_database():
        log.debug('Simulate redo history')
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        wxgui_api.simulate_redo_tree(no_confirm=True)
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def create_item():
    if _select_database():
        _select_items(False)

        if random.randint(0, 1) == 0:
            log.debug('Simulate create sibling item')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_create_sibling()
        else:
            log.debug('Simulate create child item')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_create_child()
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def cut_items():
    if wxcopypaste_api and _select_database():
        if _select_items(True):
            log.debug('Simulate cut items')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxcopypaste_api.simulate_cut_items(no_confirm=True)
        else:
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            return False
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def copy_items():
    if wxcopypaste_api and _select_database():
        if _select_items(True):
            log.debug('Simulate copy items')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxcopypaste_api.simulate_copy_items()
        else:
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            return False
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def paste_items():
    if wxcopypaste_api and _select_database():
        _select_items(False)

        if random.randint(0, 1) == 0:
            log.debug('Simulate paste items as siblings')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxcopypaste_api.simulate_paste_items_as_siblings()
        else:
            log.debug('Simulate paste items as children')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxcopypaste_api.simulate_paste_items_as_children()
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def move_item():
    if _select_database():
        if _select_items(False):
            c = random.randint(0, 2)
            if c == 0:
                log.debug('Simulate move item up')
                # Databases are blocked in simulator._do_action
                core_api.release_databases()
                wxgui_api.simulate_move_item_up()
            elif c == 1:
                log.debug('Simulate move item down')
                # Databases are blocked in simulator._do_action
                core_api.release_databases()
                wxgui_api.simulate_move_item_down()
            else:
                log.debug('Simulate move item to parent')
                # Databases are blocked in simulator._do_action
                core_api.release_databases()
                wxgui_api.simulate_move_item_to_parent()
        else:
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            return False
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def edit_item():
    if _select_database():
        if _select_items(False):
            log.debug('Simulate edit item')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_edit_item()
        else:
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            return False
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def delete_items():
    if _select_database():
        if _select_items(True):
            log.debug('Simulate delete items')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_delete_items(no_confirm=True)
        else:
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            return False
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def edit_editor_text():
    if _select_editor():
        text = ''
        words = ('the quick brown fox jumps over the lazy dog ' * 6).split()
        seps = ' ' * 6 + '\n'
        for x in range(random.randint(10, 100)):
            words.append(str(random.randint(0, 100)))
            text = ''.join((text, random.choice(words),
                            random.choice(seps)))
        text = ''.join((text, random.choice(words))).capitalize()

        log.debug('Simulate replace editor text')
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        wxgui_api.simulate_replace_editor_text(text)
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def edit_editor_rules():
    if wxscheduler_api and wxscheduler_basicrules_api and _select_editor():
        filename, id_ = wxgui_api.get_active_editor()

        wxscheduler_api.simulate_expand_rules_panel(filename, id_)
        wxscheduler_api.simulate_remove_all_rules(filename, id_)

        rules = []

        for n in range(random.randint(0, 8)):
            start = int((random.gauss(time.time(), 15000)) // 60 * 60)
            end = random.choice((None, start + random.randint(1, 360) * 60))
            ralarm = random.choice((None, 0))
            rstart = random.randint(0, 1440) * 60
            # Ignore 'days', 'weeks', 'months', 'years'
            rendu = random.choice(('minutes', 'hours'))
            if rendu == 'minutes':
                rendn = random.randint(1, 360)
            elif rendu == 'hours':
                rendn = random.randint(1, 24)
            inclusive = random.choice((True, False))

            rule = random.choice((
                {'rule': 'occur_once',
                 'start': start,
                 'end': end,
                 'ralarm': ralarm},
                {'rule': 'occur_every_day',
                 'rstart': rstart,
                 'rendn': rendn,
                 'rendu': rendu,
                 'ralarm': ralarm},
                {'rule': 'except_once',
                 'start': start,
                 'end': end,
                 'inclusive': inclusive}
            ))

            rules.append(rule)

        log.debug('Simulate replace item rules')
        # Databases are blocked in simulator._do_action
        core_api.release_databases()

        for rule in rules:
            if rule['rule'] == 'occur_once':
                wxscheduler_basicrules_api.simulate_create_occur_once_rule(
                                                   filename, id_, rule['start'],
                                                    rule['end'], rule['ralarm'])
            elif rule['rule'] == 'occur_every_day':
                wxscheduler_basicrules_api.simulate_create_occur_every_day_rule(
                                   filename, id_, rule['rstart'], rule['rendn'],
                                                  rule['rendu'], rule['ralarm'])
            elif rule['rule'] == 'except_once':
                wxscheduler_basicrules_api.simulate_create_except_once_rule(
                                                   filename, id_, rule['start'],
                                                 rule['end'], rule['inclusive'])
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def apply_editor():
    if _select_editor():
        if random.randint(0, 9) < 9:
            log.debug('Simulate apply editor')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_apply_editor()
        else:
            log.debug('Simulate apply all editors')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxgui_api.simulate_apply_all_editors()
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def close_editor():
    if _select_editor():
        apply_ = random.randint(0, 5)
        if random.randint(0, 9) < 9:
            log.debug('Simulate' + (' apply and ' if apply_ > 0 else ' ') +
                                                                 'close editor')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            if apply_ > 0:
                wxgui_api.simulate_apply_editor()
            wxgui_api.simulate_close_editor(ask='quiet')
        else:
            log.debug('Simulate' + (' apply and ' if apply_ > 0 else ' ') +
                                                            'close all editors')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            if apply_ > 0:
                wxgui_api.simulate_apply_all_editors()
            wxgui_api.simulate_close_all_editors(ask='quiet')
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def snooze_alarms():
    alarms = wxalarms_api.get_active_alarms()
    if wxalarms_api and alarms:
        # Ignore 'days', 'weeks', 'months', 'years'
        unit = random.choice(('minutes', 'hours'))
        if unit == 'minutes':
            number = random.randint(1, 360)
        elif unit == 'hours':
            number = random.randint(1, 24)

        wxalarms_api.simulate_set_snooze_time(number, unit)

        if random.randint(0, 11) > 0:
            filename, alarmid = random.choice(alarms)
            log.debug('Simulate snooze alarm')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxalarms_api.simulate_snooze_alarm(filename, alarmid)
        else:
            log.debug('Simulate snooze all alarms')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxalarms_api.simulate_snooze_all_alarms()
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False


def dismiss_alarms():
    alarms = wxalarms_api.get_active_alarms()
    if wxalarms_api and alarms:
        if random.randint(0, 11) > 0:
            filename, alarmid = random.choice(alarms)
            log.debug('Simulate dismiss alarm')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxalarms_api.simulate_dismiss_alarm(filename, alarmid)
        else:
            log.debug('Simulate dismiss all alarms')
            # Databases are blocked in simulator._do_action
            core_api.release_databases()
            wxalarms_api.simulate_dismiss_all_alarms()
    else:
        # Databases are blocked in simulator._do_action
        core_api.release_databases()
        return False