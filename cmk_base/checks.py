#!/usr/bin/env python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2014             mk@mathias-kettner.de |
# +------------------------------------------------------------------+
#
# This file is part of Check_MK.
# The official homepage is at http://mathias-kettner.de/check_mk.
#
# check_mk is free software;  you can redistribute it and/or modify it
# under the  terms of the  GNU General Public License  as published by
# the Free Software Foundation in version 2.  check_mk is  distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;  with-
# out even the implied warranty of  MERCHANTABILITY  or  FITNESS FOR A
# PARTICULAR PURPOSE. See the  GNU General Public License for more de-
# tails. You should have  received  a copy of the  GNU  General Public
# License along with GNU Make; see the file  COPYING.  If  not,  write
# to the Free Software Foundation, Inc., 51 Franklin St,  Fifth Floor,
# Boston, MA 02110-1301 USA.

import os
import math

import cmk.paths
import cmk.render as render
from cmk.exceptions import MKGeneralException

import cmk_base
import cmk_base.utils
import cmk_base.rulesets as rulesets
import cmk_base.config as config
import cmk_base.console as console
import cmk_base.snmp as snmp
import cmk_base.item_state as item_state

# TODO: Cleanup access to check_info[] -> replace it by different function calls
# like for example check_exists(...)

# The following data structures will be filled by the checks
check_info                         = {} # all known checks
check_includes                     = {} # library files needed by checks
precompile_params                  = {} # optional functions for parameter precompilation
check_default_levels               = {} # dictionary-configured checks declare their default level variables here
factory_settings                   = {} # factory settings for dictionary-configured checks
check_config_variables             = [] # variables (names) in checks/* needed for check itself
snmp_info                          = {} # whichs OIDs to fetch for which check (for tabular information)
snmp_scan_functions                = {} # SNMP autodetection
active_check_info                  = {} # definitions of active "legacy" checks
special_agent_info                 = {}

# Now read in all checks. Note: this is done *before* reading the
# configuration, because checks define variables with default
# values user can override those variables in his configuration.
# If a check or check.include is both found in local/ and in the
# normal structure, then only the file in local/ must be read!
def load():
    filelist = plugin_pathnames_in_directory(cmk.paths.local_checks_dir) \
             + plugin_pathnames_in_directory(cmk.paths.checks_dir)

    # read include files always first, but still in the sorted
    # order with local ones last (possibly overriding variables)
    filelist = [ f for f in filelist if f.endswith(".include") ] + \
               [ f for f in filelist if not f.endswith(".include") ]

    varname = None
    value = None
    ignored_variable_types = [ type(lambda: None), type(os) ]

    known_vars = set(globals().keys()) # track new configuration variables

    loaded_files = set()
    for f in filelist:
        if not f.endswith("~"): # ignore emacs-like backup files
            file_name = f.rsplit("/", 1)[-1]
            if file_name not in loaded_files:
                try:
                    loaded_files.add(file_name)
                    execfile(f, globals())
                except Exception, e:
                    console.error("Error in plugin file %s: %s\n", f, e)
                    if cmk.debug.enabled():
                        raise

    for varname, value in globals().iteritems():
        if varname[0] != '_' \
           and varname not in known_vars \
           and type(value) not in ignored_variable_types:
            config.register(varname, value)

    # Now convert check_info to new format.
    convert_check_info()
    verify_checkgroup_members()
    initialize_check_type_caches()


def plugin_pathnames_in_directory(path):
    if path and os.path.exists(path):
        return sorted([
            path + "/" + f
            for f in os.listdir(path)
            if not f.startswith(".")
        ])
    else:
        return []


# FIXME: Clear / unset all legacy variables to prevent confusions in other code trying to
# use the legacy variables which are not set by newer checks.
def convert_check_info():
    check_info_defaults = {
        "check_function"          : check_unimplemented,
        "inventory_function"      : None,
        "parse_function"          : None,
        "group"                   : None,
        "snmp_info"               : None,
        "snmp_scan_function"      : None,
        "handle_empty_info"       : False,
        "handle_real_time_checks" : False,
        "default_levels_variable" : None,
        "node_info"               : False,
        "extra_sections"          : [],
        "service_description"     : None,
        "has_perfdata"            : False,
    }

    for check_type, info in check_info.items():
        basename = check_type.split(".")[0]

        if type(info) != dict:
            # Convert check declaration from old style to new API
            check_function, service_description, has_perfdata, inventory_function = info
            if inventory_function == no_discovery_possible:
                inventory_function = None

            check_info[check_type] = {
                "check_function"          : check_function,
                "service_description"     : service_description,
                "has_perfdata"            : not not has_perfdata,
                "inventory_function"      : inventory_function,
                # Insert check name as group if no group is being defined
                "group"                   : check_type,
                "snmp_info"               : snmp_info.get(check_type),
                # Sometimes the scan function is assigned to the check_type
                # rather than to the base name.
                "snmp_scan_function"      :
                    snmp_scan_functions.get(check_type,
                        snmp_scan_functions.get(basename)),
                "handle_empty_info"       : False,
                "handle_real_time_checks" : False,
                "default_levels_variable" : check_default_levels.get(check_type),
                "node_info"               : False,
                "parse_function"          : None,
                "extra_sections"          : [],
            }
        else:
            # Ensure that there are only the known keys set. Is meant to detect typos etc.
            for key in info.keys():
                if key != "includes" and key not in check_info_defaults:
                    raise MKGeneralException("The check '%s' declares an unexpected key '%s' in 'check_info'." %
                                                                                    (check_type, key))

            # Check does already use new API. Make sure that all keys are present,
            # extra check-specific information into file-specific variables.
            for key, val in check_info_defaults.items():
                info.setdefault(key, val)

            # Include files are related to the check file (= the basename),
            # not to the (sub-)check. So we keep them in check_includes.
            check_includes.setdefault(basename, [])
            check_includes[basename] += info.get("includes", [])

    # Make sure that setting for node_info of check and subcheck matches
    for check_type, info in check_info.iteritems():
        if "." in check_type:
            base_check = check_type.split(".")[0]
            if base_check not in check_info:
                if info["node_info"]:
                    raise MKGeneralException("Invalid check implementation: node_info for %s is True, but base check %s not defined" %
                        (check_type, base_check))
            elif check_info[base_check]["node_info"] != info["node_info"]:
               raise MKGeneralException("Invalid check implementation: node_info for %s and %s are different." % (
                   (base_check, check_type)))

    # Now gather snmp_info and snmp_scan_function back to the
    # original arrays. Note: these information is tied to a "agent section",
    # not to a check. Several checks may use the same SNMP info and scan function.
    for check_type, info in check_info.iteritems():
        basename = check_type.split(".")[0]
        if info["snmp_info"] and basename not in snmp_info:
            snmp_info[basename] = info["snmp_info"]
        if info["snmp_scan_function"] and basename not in snmp_scan_functions:
            snmp_scan_functions[basename] = info["snmp_scan_function"]


# This function validates the checks which are members of checkgroups to have either
# all or none an item. Mixed checkgroups lead to strange exceptions when processing
# the check parameters. So it is much better to catch these errors in a central place
# with a clear error message.
def verify_checkgroup_members():
    groups = checks_by_checkgroup()

    for group_name, checks in groups.items():
        with_item, without_item = [], []
        for check_type, check in checks:
            # Trying to detect whether or not the check has an item. But this mechanism is not
            # 100% reliable since Check_MK appends an item to the service_description when "%s"
            # is not in the checks service_description template.
            # Maybe we need to define a new rule which enforces the developer to use the %s in
            # the service_description. At least for grouped checks.
            if "%s" in check["service_description"]:
                with_item.append(check_type)
            else:
                without_item.append(check_type)

        if with_item and without_item:
            raise MKGeneralException("Checkgroup %s has checks with and without item! At least one of "
                                     "the checks in this group needs to be changed (With item: %s, "
                                     "Without item: %s)" % (group_name, ", ".join(with_item), ", ".join(without_item)))


def checks_by_checkgroup():
    groups = {}
    for check_type, check in check_info.items():
        group_name = check["group"]
        if group_name:
            groups.setdefault(group_name, [])
            groups[group_name].append((check_type, check))
    return groups


def initialize_check_type_caches():
    snmp_cache = cmk_base.runtime_cache.get_set("check_type_snmp")
    snmp_cache.update(snmp_info.keys())

    tcp_cache = cmk_base.runtime_cache.get_set("check_type_tcp")
    tcp_cache.update(check_info.keys())


def set_hostname(hostname):
    global g_hostname
    g_hostname = hostname


def set_service_description(descr):
    global g_service_description
    g_service_description = descr


#.
#   .--Check API-----------------------------------------------------------.
#   |             ____ _               _         _    ____ ___             |
#   |            / ___| |__   ___  ___| | __    / \  |  _ \_ _|            |
#   |           | |   | '_ \ / _ \/ __| |/ /   / _ \ | |_) | |             |
#   |           | |___| | | |  __/ (__|   <   / ___ \|  __/| |             |
#   |            \____|_| |_|\___|\___|_|\_\ /_/   \_\_|  |___|            |
#   |                                                                      |
#   +----------------------------------------------------------------------+
#   |  Helper API for being used in checks                                 |
#   '----------------------------------------------------------------------'
# TODO: Wrap everything in an API object

# TODO: Move imports directly to checks?
import re
import time
from cmk.regex import regex

BINARY     = snmp.BINARY
CACHED_OID = snmp.CACHED_OID

OID_END              = snmp.OID_END
OID_STRING           = snmp.OID_STRING
OID_BIN              = snmp.OID_BIN
OID_END_BIN          = snmp.OID_END_BIN
OID_END_OCTET_STRING = snmp.OID_END_OCTET_STRING
binstring_to_int     = snmp.binstring_to_int

# Is set before check execution
g_hostname            = "unknown" # Host currently being checked
g_service_description = None

def saveint(i):
    try:
        return int(i)
    except:
        return 0


def savefloat(f):
    try:
        return float(f)
    except:
        return 0.0


# The function no_discovery_possible is as stub function used for
# those checks that do not support inventory. It must be known before
# we read in all the checks
def no_discovery_possible(check_type, info):
    console.verbose("%s does not support discovery. Skipping it.\n", check_type)
    return []

service_extra_conf       = rulesets.service_extra_conf
get_age_human_readable   = render.approx_age
get_bytes_human_readable = render.bytes
quote_shell_string       = cmk_base.utils.quote_shell_string


# Similar to get_bytes_human_readable, but optimized for file
# sizes. Really only use this for files. We assume that for smaller
# files one wants to compare the exact bytes of a file, so the
# threshold to show the value as MB/GB is higher as the one of
# get_bytes_human_readable().
# TODO: Replace by some render.* function / move to render module?
def get_filesize_human_readable(size):
    if size < 4 * 1024 * 1024:
        return "%d B" % int(size)
    elif size < 4 * 1024 * 1024 * 1024:
        return "%.2f MB" % (float(size) / (1024 * 1024))
    else:
        return "%.2f GB" % (float(size) / (1024 * 1024 * 1024))


# TODO: Replace by some render.* function / move to render module?
def get_nic_speed_human_readable(speed):
    try:
        speedi = int(speed)
        if speedi == 10000000:
            speed = "10 Mbit/s"
        elif speedi == 100000000:
            speed = "100 Mbit/s"
        elif speedi == 1000000000:
            speed = "1 Gbit/s"
        elif speedi < 1500:
            speed = "%d bit/s" % speedi
        elif speedi < 1000000:
            speed = "%.1f Kbit/s" % (speedi / 1000.0)
        elif speedi < 1000000000:
            speed = "%.2f Mbit/s" % (speedi / 1000000.0)
        else:
            speed = "%.2f Gbit/s" % (speedi / 1000000000.0)
    except:
        pass
    return speed


# TODO: Replace by some render.* function / move to render module?
def get_timestamp_human_readable(timestamp):
    if timestamp:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(timestamp)))
    else:
        return "never"


# TODO: Replace by some render.* function / move to render module?
def get_relative_date_human_readable(timestamp):
    now = time.time()
    if timestamp > now:
        return "in " + get_age_human_readable(timestamp - now)
    else:
        return get_age_human_readable(now - timestamp) + " ago"


# Format perc (0 <= perc <= 100 + x) so that precision
# digits are being displayed. This avoids a "0.00%" for
# very small numbers
# TODO: Replace by some render.* function / move to render module?
def get_percent_human_readable(perc, precision=2):
    if perc > 0:
        perc_precision = max(1, 2 - int(round(math.log(perc, 10))))
    else:
        perc_precision = 1
    return "%%.%df%%%%" % perc_precision % perc


#
# Counter handling
#

set_item_state     = item_state.set_item_state
get_item_state     = item_state.get_item_state
clear_item_state   = item_state.clear_item_state
get_rate           = item_state.get_rate
get_average        = item_state.get_average
# TODO: Cleanup checks and deprecate this
last_counter_wrap  = item_state.last_counter_wrap

SKIP  = item_state.SKIP
RAISE = item_state.RAISE
ZERO  = item_state.ZERO

MKCounterWrapped = item_state.MKCounterWrapped

def check_levels(value, dsname, params, unit="", factor=1.0, scale=1.0, statemarkers=False):
    """Generic function for checking a value against levels

    This also supports predictive levels.

    value:   currently measured value
    dsname:  name of the datasource in the RRD that corresponds to this value
    unit:    unit to be displayed in the plugin output, e.g. "MB/s"
    factor:  the levels are multiplied with this factor before applying
             them to the value. This is being used for the CPU load check
             currently. The levels here are "per CPU", so the number of
             CPUs is used as factor.
    scale:   Scale of the levels in relation to "value" and the value in the RRDs.
             For example if the levels are specified in GB and the RRD store KB, then
             the scale is 1024*1024.
    """
    if unit:
        unit = " " + unit # Insert space before MB, GB, etc.
    perfdata = []
    infotexts = []

    def scale_value(v):
        if v == None:
            return None
        else:
            return v * factor * scale

    def levelsinfo_ty(ty, warn, crit, unit):
        return ("warn/crit %s %.2f/%.2f %s" % (ty, warn, crit, unit)).strip()

    # None or (None, None) -> do not check any levels
    if params == None or params == (None, None):
        return 0, "", []

    # Pair of numbers -> static levels
    elif type(params) == tuple:
        if len(params) == 2: # upper warn and crit
            warn_upper, crit_upper = scale_value(params[0]), scale_value(params[1])
            warn_lower, crit_lower = None, None

        else: # upper and lower warn and crit
            warn_upper, crit_upper = scale_value(params[0]), scale_value(params[1])
            warn_lower, crit_lower = scale_value(params[2]), scale_value(params[3])

        ref_value = None

    # Dictionary -> predictive levels
    else:
        try:
            ref_value, ((warn_upper, crit_upper), (warn_lower, crit_lower)) = \
                cmk_base.prediction.get_levels(g_hostname, g_service_description,
                                dsname, params, "MAX", levels_factor=factor * scale)

            if ref_value:
                infotexts.append("predicted reference: %.2f%s" % (ref_value / scale, unit))
            else:
                infotexts.append("no reference for prediction yet")

        except MKGeneralException, e:
            ref_value = None
            warn_upper, crit_upper, warn_lower, crit_lower = None, None, None, None
            infotexts.append("no reference for prediction (%s)" % e)

        except Exception, e:
            if cmk.debug.enabled():
                raise
            return 3, "%s" % e, []

    if ref_value:
        perfdata.append(('predict_' + dsname, ref_value))

    # Critical cases
    if crit_upper != None and value >= crit_upper:
        state = 2
        infotexts.append(levelsinfo_ty("at", warn_upper / scale, crit_upper / scale, unit))
    elif crit_lower != None and value < crit_lower:
        state = 2
        infotexts.append(levelsinfo_ty("below", warn_lower / scale, crit_lower / scale, unit))

    # Warning cases
    elif warn_upper != None and value >= warn_upper:
        state = 1
        infotexts.append(levelsinfo_ty("at", warn_upper / scale, crit_upper / scale, unit))
    elif warn_lower != None and value < warn_lower:
        state = 1
        infotexts.append(levelsinfo_ty("below", warn_lower / scale, crit_lower / scale, unit))

    # OK
    else:
        state = 0

    if infotexts:
        infotext = " (" + ", ".join(infotexts) + ")"
    else:
        infotext = ""

    if state and statemarkers:
        if state == 1:
            infotext += "(!)"
        else:
            infotext += "(!!)"

    return state, infotext, perfdata


# retrive the service level that applies to the calling check.
def get_effective_service_level():
    service_levels = rulesets.service_extra_conf(g_hostname, g_service_description,
                                        service_service_levels)

    if service_levels:
        return service_levels[0]
    else:
        service_levels = rulesets.host_extra_conf(g_hostname, host_service_levels)
        if service_levels:
            return service_levels[0]
    return 0


# like time.mktime but assumes the time_struct to be in utc, not in local time.
def utc_mktime(time_struct):
    import calendar
    return calendar.timegm(time_struct)


def passwordstore_get_cmdline(fmt, pw):
    if type(pw) != tuple:
        pw = ("password", pw)

    if pw[0] == "password":
        return fmt % pw[1]
    else:
        return ("store", pw[1], fmt)


# Use this function to get the age of the agent data cache file
# of tcp or snmp hosts or None in case of piggyback data because
# we do not exactly know the latest agent data. Maybe one time
# we can handle this. For cluster hosts an exception is raised.
def get_agent_data_time():
    return agent_cache_file_age(g_hostname, g_check_type)


def agent_cache_file_age(hostname, check_type):
    if is_cluster(hostname):
        raise MKGeneralException("get_agent_data_time() not valid for cluster")

    if is_snmp_check(check_type):
        cachefile = cmk.paths.tcp_cache_dir + "/" + hostname + "." + check_type.split(".")[0]
    elif is_tcp_check(check_type):
        cachefile = cmk.paths.tcp_cache_dir + "/" + hostname
    else:
        cachefile = None

    if cachefile is not None and os.path.exists(cachefile):
        return cachefile_age(cachefile)
    else:
        return None
