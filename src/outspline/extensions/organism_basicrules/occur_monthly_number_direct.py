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

import time as _time
import datetime as _datetime

from exceptions import BadRuleError

_RULE_NAMES = {'local': 'occur_monthly_number_direct_local',
               'UTC': 'occur_monthly_number_direct_UTC'}


def make_rule(months, day, hour, minute, rend, ralarm, standard, guiconfig):
    """
    @param months: The months for which create occurrences: must be a list of
                   integers representing the selected months (1 - 12).
    @param day: The month day number when to start an occurrence (1 - 31).
    @param hour: The hour when to start an occurrence (0 - 23).
    @param minute: The minute when to start an occurrence (0 - 59).
    @param rend: The positive difference in seconds between the relative start
                 time and the relative end time.
    @param ralarm: The difference in seconds between the relative start time
                   and the relative alarm time; it is negative if the alarm is
                   set later than the start time.
    @param standard: The time standard to be used, either 'local' or 'UTC'.
    @param guiconfig: A place to store any configuration needed only by the
                      interface.
    """
    # Do not use a rstart calculated from the start of the month (which would
    #   replace day, hour and minute) because the months with a DST time change
    #   have a variable length
    # Make sure this rule can only produce occurrences compliant with the
    #   requirements defined in organism_api.update_item_rules
    # There's no need to check standard because it's imposed by the API
    if isinstance(months, list) and len(months) > 0 and \
                isinstance(day, int) and 0 < day < 32 and \
                isinstance(hour, int) and -1 < hour < 24 and \
                isinstance(minute, int) and -1 < minute < 60 and \
                (rend is None or (isinstance(rend, int) and rend > 0)) and \
                (ralarm is None or isinstance(ralarm, int)):

        for m in months:
            if not isinstance(m, int) or m < 1 or m > 12:
                raise BadRuleError()

        nmonths = []

        for n in xrange(1, 13):
            if n in months:
                nmonths.extend([n, ] * (n - len(nmonths)))
        # Note that it's ok that nmonths can be shorter than 12 items; do *not*
        # do the following:
        #else:
        #    nmonths.extend([nmonths[0], ] * (12 - len(nmonths)))

        # Calculate the shortest time difference with the end of a month
        #  (consider 27 days to make up for possible DST or time zone changes:
        #  for this reason diff may be negative; the number 28 is due to the
        #  fact that 1 must be re-added because day starts from 1, not 0)
        diff = (28 - day) * 86400 - hour * 3600 - minute * 60
        diffs = max(diff, 0)

        # Also take a possible negative (late) alarm time into account, in fact
        #  the occurrence wouldn't be found if the search range included the
        #  alarm time but not the actual occurrence time span; remember that
        #  it's normal that the occurrence is not added to the results if the
        #  search range is between (and doesn't include) the alarm time and the
        #  actual occurrence time span
        if ralarm:
            srend = max(rend, ralarm * -1, 0)
        else:
            srend = max(rend, 0)

        # Don't just store the number of months to go back, because it would
        #  make the algorithm always go back also when it's not necessary
        maxoverlap = max(srend - diffs, 0)

        return {
            'rule': _RULE_NAMES[standard],
            '#': (
                maxoverlap,
                nmonths,
                day,
                hour,
                minute,
                rend,
                ralarm,
                guiconfig,
            )
        }
    else:
        raise BadRuleError()


def get_occurrences_range_local(mint, utcmint, maxt, utcoffset, filename, id_,
                                                                rule, occs):
    # Go back by span in order to keep into account any occurrence that still
    # has to end
    mintime = mint - rule['#'][0]
    months = rule['#'][1]
    startd = rule['#'][2]
    startH = rule['#'][3]
    startM = rule['#'][4]
    rend = rule['#'][5]
    ralarm = rule['#'][6]

    date = _datetime.datetime.fromtimestamp(mintime)

    try:
        month = months[date.month - 1]
    except IndexError:
        month = months[0]
        year = date.year + 1
    else:
        year = date.year

    while True:
        try:
            sdate = _datetime.datetime(year, month, startd, startH, startM)
        except ValueError:
            # Prevent infinite loops
            maxdate = _datetime.date.fromtimestamp(maxt)
            testdate = _datetime.date(year, month, 1)

            if maxdate < testdate:
                break
        else:
            start = int(_time.mktime(sdate.timetuple()))

            try:
                end = start + rend
            except TypeError:
                end = None

            try:
                alarm = start - ralarm
            except TypeError:
                alarm = None

            if start > maxt and (alarm is None or alarm > maxt):
                break

            # The rule is checked in make_rule, no need to use occs.add
            occs.add_safe({'filename': filename,
                           'id_': id_,
                           'start': start,
                           'end': end,
                           'alarm': alarm})

        try:
            month = months[month]
        except IndexError:
            month = months[0]
            year += 1


def get_occurrences_range_UTC(mint, utcmint, maxt, utcoffset, filename, id_,
                                                                rule, occs):
    # Go back by span in order to keep into account any occurrence that still
    # has to end
    mintime = mint - rule['#'][0]
    months = rule['#'][1]
    startd = rule['#'][2]
    startH = rule['#'][3]
    startM = rule['#'][4]
    rend = rule['#'][5]
    ralarm = rule['#'][6]

    # Using utcfromtimestamp gives correct behaviour in Eastern (positive) time
    # zones (e.g. Australia/Sydney)
    date = _datetime.datetime.utcfromtimestamp(mintime)

    try:
        month = months[date.month - 1]
    except IndexError:
        month = months[0]
        year = date.year + 1
    else:
        year = date.year

    while True:
        try:
            sdate = _datetime.datetime(year, month, startd, startH, startM)
        except ValueError:
            # Prevent infinite loops
            maxdate = _datetime.date.fromtimestamp(maxt)
            testdate = _datetime.date(year, month, 1)

            if maxdate < testdate:
                break
        else:
            start = int(_time.mktime(sdate.timetuple()))

            # Every timestamp can have a different UTC offset, depending
            # whether it's in a DST period or not
            offset = utcoffset.compute(start)

            sstart = start - offset

            try:
                send = sstart + rend
            except TypeError:
                send = None

            try:
                salarm = sstart - ralarm
            except TypeError:
                salarm = None

            # Do compare sstart and salarm with maxt, *not* start and alarm
            if sstart > maxt and (salarm is None or salarm > maxt):
                break

            # The rule is checked in make_rule, no need to use occs.add
            occs.add_safe({'filename': filename,
                           'id_': id_,
                           'start': sstart,
                           'end': send,
                           'alarm': salarm})

        try:
            month = months[month]
        except IndexError:
            month = months[0]
            year += 1


def get_next_item_occurrences_local(base_time, utcbase, utcoffset, filename,
                                                            id_, rule, occs):
    # Go back by span in order to keep into account any occurrence that still
    # has to end
    mintime = base_time - rule['#'][0]
    months = rule['#'][1]
    startd = rule['#'][2]
    startH = rule['#'][3]
    startM = rule['#'][4]
    rend = rule['#'][5]
    ralarm = rule['#'][6]

    date = _datetime.datetime.fromtimestamp(mintime)

    try:
        month = months[date.month - 1]
    except IndexError:
        month = months[0]
        year = date.year + 1
    else:
        year = date.year

    while True:
        try:
            sdate = _datetime.datetime(year, month, startd, startH, startM)
        except ValueError:
            # Prevent infinite loops
            testdate = _datetime.date(year, month, 1)
            next_ = occs.get_next_occurrence_time()

            if next_:
                maxdate = _datetime.date.fromtimestamp(next_)
            else:
                # Note the 4-week limit, otherwise if this was the only
                # existing rule, but it couldn't generate valid occurrences
                # (e.g. 31 February only), it would trigger an infinite loop
                maxdate = _datetime.date.fromtimestamp(base_time) + \
                                                _datetime.timedelta(weeks=4)

            if maxdate < testdate:
                break
        else:
            start = int(_time.mktime(sdate.timetuple()))

            try:
                end = start + rend
            except TypeError:
                end = None

            try:
                alarm = start - ralarm
            except TypeError:
                alarm = None

            occd = {'filename': filename,
                    'id_': id_,
                    'start': start,
                    'end': end,
                    'alarm': alarm}

            next_occ = occs.get_next_occurrence_time()

            # The rule is checked in make_rule, no need to use occs.add
            if occs.add_safe(base_time, occd) or (next_occ and
                                        start > next_occ and
                                        (alarm is None or alarm > next_occ)):
                break

        try:
            month = months[month]
        except IndexError:
            month = months[0]
            year += 1


def get_next_item_occurrences_UTC(base_time, utcbase, utcoffset, filename,
                                                            id_, rule, occs):
    # Go back by span in order to keep into account any occurrence that still
    # has to end
    mintime = base_time - rule['#'][0]
    months = rule['#'][1]
    startd = rule['#'][2]
    startH = rule['#'][3]
    startM = rule['#'][4]
    rend = rule['#'][5]
    ralarm = rule['#'][6]

    # Using utcfromtimestamp gives correct behaviour in Eastern (positive) time
    # zones (e.g. Australia/Sydney)
    date = _datetime.datetime.utcfromtimestamp(mintime)

    try:
        month = months[date.month - 1]
    except IndexError:
        month = months[0]
        year = date.year + 1
    else:
        year = date.year

    while True:
        try:
            sdate = _datetime.datetime(year, month, startd, startH, startM)
        except ValueError:
            # Prevent infinite loops
            testdate = _datetime.date(year, month, 1)
            next_ = occs.get_next_occurrence_time()

            if next_:
                maxdate = _datetime.date.fromtimestamp(next_)
            else:
                # Note the 4-week limit, otherwise if this was the only
                # existing rule, but it couldn't generate valid occurrences
                # (e.g. 31 February only), it would trigger an infinite loop
                maxdate = _datetime.date.fromtimestamp(base_time) + \
                                                _datetime.timedelta(weeks=4)

            if maxdate < testdate:
                break
        else:
            start = int(_time.mktime(sdate.timetuple()))

            # Every timestamp can have a different UTC offset, depending
            # whether it's in a DST period or not
            offset = utcoffset.compute(start)

            sstart = start - offset

            try:
                send = sstart + rend
            except TypeError:
                send = None

            try:
                salarm = sstart - ralarm
            except TypeError:
                salarm = None

            occd = {'filename': filename,
                    'id_': id_,
                    'start': sstart,
                    'end': send,
                    'alarm': salarm}

            next_occ = occs.get_next_occurrence_time()

            # The rule is checked in make_rule, no need to use occs.add
            # Do compare sstart and salarm with next_occ, *not* start and alarm
            if occs.add_safe(base_time, occd) or (next_occ and
                            sstart > next_occ and
                            (salarm is None or salarm > next_occ)):
                break

        try:
            month = months[month]
        except IndexError:
            month = months[0]
            year += 1
