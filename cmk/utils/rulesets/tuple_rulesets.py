#!/usr/bin/env python
# -*- encoding: utf-8; py-indent-offset: 4 -*-
# +------------------------------------------------------------------+
# |             ____ _               _        __  __ _  __           |
# |            / ___| |__   ___  ___| | __   |  \/  | |/ /           |
# |           | |   | '_ \ / _ \/ __| |/ /   | |\/| | ' /            |
# |           | |___| | | |  __/ (__|   <    | |  | | . \            |
# |            \____|_| |_|\___|\___|_|\_\___|_|  |_|_|\_\           |
# |                                                                  |
# | Copyright Mathias Kettner 2019             mk@mathias-kettner.de |
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
from typing import NamedTuple, Generator, Dict, Text, Pattern, Tuple, List  # pylint: disable=unused-import

from cmk.utils.regex import regex
import cmk.utils.paths
from cmk.utils.exceptions import MKGeneralException

# Conveniance macros for legacy tuple based host and service rules
PHYSICAL_HOSTS = ['@physical']  # all hosts but not clusters
CLUSTER_HOSTS = ['@cluster']  # all cluster hosts
ALL_HOSTS = ['@all']  # physical and cluster hosts
ALL_SERVICES = [""]  # optical replacement"
NEGATE = '@negate'  # negation in boolean lists

# TODO: We could make some more optimizations to host/item list matching:
# - Is it worth to detect matches that are no regex matches?
# - We could remove .* from end of regexes
# - What's about compilation of the regexes?

RulesetMatchObject = NamedTuple("RulesetMatchObject", [
    ("host_name", str),
    ("service_description", Text),
])


def get_rule_options(entry):
    """Get the options from a rule.

    Pick out the option element of a rule. Currently the options "disabled"
    and "comments" are being honored."""
    if isinstance(entry[-1], dict):
        return entry[:-1], entry[-1]

    return entry, {}


class RulesetMatcher(object):
    """Performing matching on host / service rulesets

    There is some duplicate logic for host / service rulesets. This has been
    kept for performance reasons. Especially the service rulset matching is
    done very often in large setups. Be careful when working here.
    """

    def __init__(self, config_cache):
        super(RulesetMatcher, self).__init__()
        self._config_cache = config_cache

        self.tuple_transformer = RulesetToDictTransformer(
            tag_to_group_map=config_cache.get_tag_to_group_map())
        self.ruleset_optimizer = RulesetOptimizier(config_cache)
        self._service_match_cache = {}

    def is_matching_host_ruleset(self, match_object, ruleset):
        # type: (RulesetMatchObject, List[Dict]) -> bool
        """Compute outcome of a ruleset set that just says yes/no

        The binary match only cares about the first matching rule of an object.
        Depending on the value the outcome is negated or not.

        Replaces in_binary_hostlist / in_boolean_serviceconf_list"""
        for value in self.get_host_ruleset_values(match_object, ruleset, is_binary=True):
            return value
        return False  # no match. Do not ignore

    def get_host_ruleset_merged_dict(self, match_object, ruleset):
        # type: (RulesetMatchObject, List[Dict]) -> Dict
        """Returns a dictionary of the merged dict values of the matched rules
        The first dict setting a key defines the final value.

        Replaces host_extra_conf_merged / service_extra_conf_merged"""
        merged_dict = {}  # type: Dict
        for rule_dict in self.get_host_ruleset_values(match_object, ruleset, is_binary=False):
            for key, value in rule_dict.items():
                merged_dict.setdefault(key, value)
        return merged_dict

    def get_host_ruleset_values(self, match_object, ruleset, is_binary):
        # type: (RulesetMatchObject, List, bool) -> Generator
        """Returns a generator of the values of the matched rules
        Replaces host_extra_conf"""
        self.tuple_transformer.transform_in_place(ruleset, is_service=False, is_binary=is_binary)

        # When the requested host is part of the local sites configuration,
        # then use only the sites hosts for processing the rules
        with_foreign_hosts = match_object.host_name not in self._config_cache.all_processed_hosts()
        optimized_ruleset = self.ruleset_optimizer.get_host_ruleset(
            ruleset, with_foreign_hosts, is_binary=is_binary)

        for value in optimized_ruleset.get(match_object.host_name, []):
            yield value

    def is_matching_service_ruleset(self, match_object, ruleset):
        # type: (RulesetMatchObject, List[Dict]) -> bool
        """Compute outcome of a ruleset set that just says yes/no

        The binary match only cares about the first matching rule of an object.
        Depending on the value the outcome is negated or not.

        Replaces in_binary_hostlist / in_boolean_serviceconf_list"""
        for value in self.get_service_ruleset_values(match_object, ruleset, is_binary=True):
            return value
        return False  # no match. Do not ignore

    def get_service_ruleset_merged_dict(self, match_object, ruleset):
        # type: (RulesetMatchObject, List[Dict]) -> Dict
        """Returns a dictionary of the merged dict values of the matched rules
        The first dict setting a key defines the final value.

        Replaces host_extra_conf_merged / service_extra_conf_merged"""
        merged_dict = {}  # type: Dict
        for rule_dict in self.get_service_ruleset_values(match_object, ruleset, is_binary=False):
            for key, value in rule_dict.items():
                merged_dict.setdefault(key, value)
        return merged_dict

    def get_service_ruleset_values(self, match_object, ruleset, is_binary):
        # type: (RulesetMatchObject, List, bool) -> Generator
        """Returns a generator of the values of the matched rules
        Replaces service_extra_conf"""
        self.tuple_transformer.transform_in_place(ruleset, is_service=True, is_binary=is_binary)

        with_foreign_hosts = match_object.host_name not in self._config_cache.all_processed_hosts()
        optimized_ruleset = self.ruleset_optimizer.get_service_ruleset(
            ruleset, with_foreign_hosts, is_binary=is_binary)

        for value, hosts, service_conditions in optimized_ruleset:
            if match_object.host_name not in hosts:
                continue

            descr_cache_id = match_object.service_description, service_conditions
            if descr_cache_id in self._service_match_cache:
                match = self._service_match_cache[descr_cache_id]
            else:
                match = self._matches_service_conditions(service_conditions,
                                                         match_object.service_description)
                self._service_match_cache[descr_cache_id] = match

            if match:
                yield value

    def _matches_service_conditions(self, service_conditions, service_description):
        # type: (Tuple[bool, Pattern[Text]], Text) -> bool
        negate, pattern = service_conditions
        if pattern.match(service_description) is not None:
            return not negate
        return negate

    # TODO: Find a way to use the generic get_values
    def get_values_for_generic_agent_host(self, ruleset):
        """Compute ruleset for "generic" host

        This fictious host has no name and no tags. It matches all rules that
        do not require specific hosts or tags. But it matches rules that e.g.
        except specific hosts or tags (is not, has not set)
        """
        self.tuple_transformer.transform_in_place(ruleset, is_service=False, is_binary=False)
        entries = []
        for rule in ruleset:
            if "options" in rule and "disabled" in rule["options"]:
                continue

            hostlist = rule["condition"].get("host_name")
            tags = rule["condition"].get("host_tags", {})

            # TODO: Fix scope
            if tags and not self.ruleset_optimizer._matches_host_tags([], tags):
                continue

            # TODO: Fix scope
            if not self.ruleset_optimizer._matches_host_name(hostlist, ""):
                continue

            entries.append(rule["value"])
        return entries


def in_servicematcher_list(service_conditions, item):
    # type: (Tuple[bool, Pattern[Text]], Text) -> bool
    negate, pattern = service_conditions
    if pattern.match(item) is not None:
        return not negate
    return negate


class RulesetOptimizier(object):
    def __init__(self, config_cache):
        super(RulesetOptimizier, self).__init__()
        self._config_cache = config_cache

        self._service_ruleset_cache = {}
        self._host_ruleset_cache = {}
        self._all_matching_hosts_match_cache = {}

        # Reference dirname -> hosts in this dir including subfolders
        self._folder_host_lookup = {}
        # All used folders used for various set intersection operations
        self._folder_path_set = set()
        # Provides a list of hosts with the same hosttags, excluding the folder
        self._hosts_grouped_by_tags = {}
        # Reference hostname -> tag group reference
        self._host_grouped_ref = {}

        # TODO: The folder will not be part of new dict tags anymore. This can
        # be cleaned up then.
        self._hosttags_without_folder = {}

        # TODO: Clean this one up?
        self._initialize_host_lookup()

    def get_host_ruleset(self, ruleset, with_foreign_hosts, is_binary):
        cache_id = id(ruleset), with_foreign_hosts

        if cache_id in self._host_ruleset_cache:
            return self._host_ruleset_cache[cache_id]

        ruleset = self._convert_host_ruleset(ruleset, with_foreign_hosts, is_binary)
        self._host_ruleset_cache[cache_id] = ruleset
        return ruleset

    def _convert_host_ruleset(self, ruleset, with_foreign_hosts, is_binary):
        """Precompute host lookup map

        Instead of a ruleset like list structure with precomputed host lists we compute a
        direct map for hostname based lookups for the matching rule values
        """
        host_values = {}
        for rule in ruleset:
            if "options" in rule and "disabled" in rule["options"]:
                continue

            for hostname in self._all_matching_hosts(rule["condition"], with_foreign_hosts):
                host_values.setdefault(hostname, []).append(rule["value"])

        return host_values

    def get_service_ruleset(self, ruleset, with_foreign_hosts, is_binary):
        cache_id = id(ruleset), with_foreign_hosts

        if cache_id in self._service_ruleset_cache:
            return self._service_ruleset_cache[cache_id]

        cached_ruleset = self._convert_service_ruleset(
            ruleset, with_foreign_hosts=with_foreign_hosts, is_binary=is_binary)
        self._service_ruleset_cache[cache_id] = cached_ruleset
        return cached_ruleset

    def _convert_service_ruleset(self, ruleset, with_foreign_hosts, is_binary):
        new_rules = []
        for rule in ruleset:
            if "options" in rule and "disabled" in rule["options"]:
                continue

            # Directly compute set of all matching hosts here, this will avoid
            # recomputation later
            hosts = self._all_matching_hosts(rule["condition"], with_foreign_hosts)

            # And now preprocess the configured patterns in the servlist
            new_rules.append(
                (rule["value"], hosts,
                 self._convert_pattern_list(rule["condition"].get("service_description"))))

        return new_rules

    def _convert_pattern_list(self, patterns):
        # type: (List[Text]) -> Tuple[bool, Pattern[Text]]
        """Compiles a list of service match patterns to a to a single regex

        Reducing the number of individual regex matches improves the performance dramatically.
        This function assumes either all or no pattern is negated (like WATO creates the rules).
        """
        if not patterns:
            return False, regex(u"")  # Match everything

        negate = False
        if isinstance(patterns, dict) and "$nor" in patterns:
            negate = True
            patterns = patterns["$nor"]

        pattern_parts = []
        for p in patterns:
            if isinstance(p, dict):
                pattern_parts.append(p["$regex"])
            else:
                pattern_parts.append(p)

        return negate, regex("(?:%s)" % "|".join("(?:%s)" % p for p in pattern_parts))

    def _all_matching_hosts(self, condition, with_foreign_hosts):
        """Returns a set containing the names of hosts that match the given
        tags and hostlist conditions."""
        hostlist = condition.get("host_name")
        tags = condition.get("host_tags", {})
        rule_path = condition.get("host_folder", "/")

        cache_id = self._condition_cache_id(hostlist, tags, rule_path), with_foreign_hosts

        try:
            return self._all_matching_hosts_match_cache[cache_id]
        except KeyError:
            pass

        if with_foreign_hosts:
            valid_hosts = self._config_cache.all_configured_hosts()
        else:
            valid_hosts = self._config_cache.all_processed_hosts()

        # Thin out the valid hosts further. If the rule is located in a folder
        # we only need the intersection of the folders hosts and the previously determined valid_hosts
        valid_hosts = self.get_hosts_within_folder(rule_path,
                                                   with_foreign_hosts).intersection(valid_hosts)

        if tags and hostlist is None:
            return self._match_hosts_by_tags(cache_id, valid_hosts, tags)

        matching = set()
        only_specific_hosts = hostlist is not None \
            and not isinstance(hostlist, dict) \
            and all(not isinstance(x, dict) for x in hostlist)

        if hostlist == []:
            pass  # Empty host list -> Nothing matches
        elif not tags and not hostlist:
            # If no tags are specified and the hostlist only include @all (all hosts)
            matching = valid_hosts
        elif not tags and only_specific_hosts:
            # If no tags are specified and there are only specific hosts we already have the matches
            matching = valid_hosts.intersection(hostlist)
        else:
            # If the rule has only exact host restrictions, we can thin out the list of hosts to check
            if only_specific_hosts:
                hosts_to_check = valid_hosts.intersection(hostlist)
            else:
                hosts_to_check = valid_hosts

            for hostname in hosts_to_check:
                # When no tag matching is requested, do not filter by tags. Accept all hosts
                # and filter only by hostlist
                if (not tags or self._matches_host_tags(
                        self._config_cache.tag_list_of_host(hostname), tags)):
                    if self._matches_host_name(hostlist, hostname):
                        matching.add(hostname)

        self._all_matching_hosts_match_cache[cache_id] = matching
        return matching

    def _matches_host_name(self, host_entries, hostname):
        if not host_entries:
            return True

        negate = False
        if isinstance(host_entries, dict) and "$nor" in host_entries:
            negate = True
            host_entries = host_entries["$nor"]

        for entry in host_entries:
            use_regex = isinstance(entry, dict)

            if hostname is True:  # -> generic agent host
                continue

            if not use_regex and hostname == entry:
                return not negate

            if use_regex and regex(entry["$regex"]).match(hostname) is not None:
                return not negate

        return negate

    def _matches_host_tags(self, hosttags, required_tags):
        for tag_id in required_tags.values():
            is_not = isinstance(tag_id, dict)
            if is_not:
                tag_id = tag_id["$ne"]

            matches = tag_id in hosttags
            if matches == is_not:
                return False

        return True

    def _condition_cache_id(self, hostlist, tags, rule_path):
        host_parts, tag_parts = [], []

        if hostlist is None:
            host_parts.append(None)
        else:
            if isinstance(hostlist, dict) and "$nor" in hostlist:
                host_parts.append("!")
                hostlist = hostlist["$nor"]

            for h in hostlist:
                if isinstance(h, dict):
                    if "$regex" not in h:
                        raise NotImplementedError()
                    host_parts.append("~%s" % h["$regex"])
                    continue

                host_parts.append(h)

        for tag_group_id, tag_id in tags.iteritems():
            val = tag_id
            if isinstance(tag_id, dict):
                if "$ne" not in tag_id:
                    raise NotImplementedError()
                val = "!%s" % tag_id["$ne"]

            tag_parts.append((tag_group_id, val))

        return tuple(sorted(host_parts)), tuple(sorted(tag_parts)), rule_path

    def _match_hosts_by_tags(self, cache_id, valid_hosts, tags):
        matching = set()
        negative_match_tags = set()
        positive_match_tags = set()
        for tag in tags.values():
            if isinstance(tag, dict):
                if "$ne" in tag:
                    negative_match_tags.add(tag["$ne"])
                else:
                    raise NotImplementedError()
            else:
                positive_match_tags.add(tag)

        # TODO:
        #if has_specific_folder_tag or self._config_cache.all_processed_hosts_similarity < 3:
        if self._config_cache.all_processed_hosts_similarity < 3:
            # Without shared folders
            for hostname in valid_hosts:
                host_tags = self._config_cache.tag_list_of_host(hostname)
                if not positive_match_tags - host_tags:
                    if not negative_match_tags.intersection(host_tags):
                        matching.add(hostname)

            self._all_matching_hosts_match_cache[cache_id] = matching
            return matching

        # With shared folders
        checked_hosts = set()
        for hostname in valid_hosts:
            if hostname in checked_hosts:
                continue

            hosts_with_same_tag = self._filter_hosts_with_same_tags_as_host(hostname, valid_hosts)
            checked_hosts.update(hosts_with_same_tag)

            tags = self._config_cache.tag_list_of_host(hostname)
            if not positive_match_tags - tags:
                if not negative_match_tags.intersection(tags):
                    matching.update(hosts_with_same_tag)

        self._all_matching_hosts_match_cache[cache_id] = matching
        return matching

    def _filter_hosts_with_same_tags_as_host(self, hostname, hosts):
        return self._hosts_grouped_by_tags[self._host_grouped_ref[hostname]].intersection(hosts)

    def get_hosts_within_folder(self, folder_path, with_foreign_hosts):
        cache_id = with_foreign_hosts, folder_path
        if cache_id not in self._folder_host_lookup:
            hosts_in_folder = set()
            relevant_hosts = self._config_cache.all_configured_hosts(
            ) if with_foreign_hosts else self._config_cache.all_processed_hosts()
            for hostname in relevant_hosts:
                if self._config_cache.host_path(hostname).startswith(folder_path):
                    hosts_in_folder.add(hostname)
            self._folder_host_lookup[cache_id] = hosts_in_folder
            return hosts_in_folder
        return self._folder_host_lookup[cache_id]

    def _initialize_host_lookup(self):
        # Determine hosts within folders
        # TODO: Cleanup this directory access for folder computation
        dirnames = [
            x[0][len(cmk.utils.paths.check_mk_config_dir):] + "/"
            for x in os.walk(cmk.utils.paths.check_mk_config_dir)
        ]
        self._folder_path_set = set(dirnames)

        # Determine hosttags without folder tag
        for hostname in self._config_cache.all_configured_hosts():
            tags_without_folder = set(self._config_cache.tag_list_of_host(hostname))
            try:
                tags_without_folder.remove(self._config_cache.host_path(hostname))
            except KeyError:
                pass

            self._hosttags_without_folder[hostname] = tags_without_folder

        # Determine hosts with same tag setup (ignoring folder tag)
        for hostname in self._config_cache.all_configured_hosts():
            group_ref = tuple(sorted(self._hosttags_without_folder[hostname]))
            self._hosts_grouped_by_tags.setdefault(group_ref, set()).add(hostname)
            self._host_grouped_ref[hostname] = group_ref


def in_extraconf_hostlist(hostlist, hostname):
    """Whether or not the given host matches the hostlist.

    Entries in list are hostnames that must equal the hostname.
    Expressions beginning with ! are negated: if they match,
    the item is excluded from the list.

    Expressions beginning with ~ are treated as regular expression.
    Also the three special tags '@all', '@clusters', '@physical'
    are allowed.
    """

    # Migration help: print error if old format appears in config file
    # FIXME: When can this be removed?
    try:
        if hostlist[0] == "":
            raise MKGeneralException('Invalid empty entry [ "" ] in configuration')
    except IndexError:
        pass  # Empty list, no problem.

    for hostentry in hostlist:
        if hostentry == '':
            raise MKGeneralException('Empty hostname in host list %r' % hostlist)
        negate = False
        use_regex = False
        if hostentry[0] == '@':
            if hostentry == '@all':
                return True
            # TODO: Is not used anymore for a long time. Will be cleaned up
            # with 1.6 tuple ruleset cleanup
            #ic = is_cluster(hostname)
            #if hostentry == '@cluster' and ic:
            #    return True
            #elif hostentry == '@physical' and not ic:
            #    return True

        # Allow negation of hostentry with prefix '!'
        else:
            if hostentry[0] == '!':
                hostentry = hostentry[1:]
                negate = True

            # Allow regex with prefix '~'
            if hostentry[0] == '~':
                hostentry = hostentry[1:]
                use_regex = True

        try:
            if not use_regex and hostname == hostentry:
                return not negate
            # Handle Regex. Note: hostname == True -> generic unknown host
            elif use_regex and hostname != True:
                if regex(hostentry).match(hostname) is not None:
                    return not negate
        except MKGeneralException:
            if cmk.utils.debug.enabled():
                raise

    return False


def hosttags_match_taglist(hosttags, required_tags):
    """Check if a host fulfills the requirements of a tag list.

    The host must have all tags in the list, except
    for those negated with '!'. Those the host must *not* have!
    A trailing + means a prefix match."""
    for tag in required_tags:
        negate, tag = _parse_negated(tag)
        if tag and tag[-1] == '+':
            tag = tag[:-1]
            matches = False
            for t in hosttags:
                if t.startswith(tag):
                    matches = True
                    break

        else:
            matches = tag in hosttags

        if matches == negate:
            return False

    return True


def convert_pattern_list(patterns):
    # type: (List[Text]) -> Tuple[bool, Pattern[Text]]
    """Compiles a list of service match patterns to a single regex

    Reducing the number of individual regex matches improves the performance dramatically.
    This function assumes either all or no pattern is negated (like WATO creates the rules).
    """
    if not patterns:
        return False, regex("")  # No pattern -> match everything

    pattern_parts = []
    negate = patterns[0].startswith("!")

    for pattern in patterns:
        # Skip ALL_SERVICES from end of negated lists
        if negate and pattern == ALL_SERVICES[0]:
            continue
        pattern_parts.append(_parse_negated(pattern)[1])

    return negate, regex("(?:%s)" % "|".join("(?:%s)" % p for p in pattern_parts))


def _parse_negated(pattern):
    # Allow negation of pattern with prefix '!'
    try:
        negate = pattern[0] == '!'
        if negate:
            pattern = pattern[1:]
    except IndexError:
        negate = False

    return negate, pattern


class RulesetToDictTransformer(object):
    """Transforms all rules in the given ruleset from the pre 1.6 tuple format to the dict format
    This is done in place to keep the references to the ruleset working.
    """

    def __init__(self, tag_to_group_map):
        super(RulesetToDictTransformer, self).__init__()
        self._tag_groups = tag_to_group_map

    def transform_in_place(self, ruleset, is_service, is_binary):
        for index, rule in enumerate(ruleset):
            if not isinstance(rule, dict):
                ruleset[index] = self._transform_rule(rule, is_service, is_binary)

    def _transform_rule(self, tuple_rule, is_service, is_binary):
        rule = {
            "condition": {},
        }

        tuple_rule = list(tuple_rule)

        # Extract optional rule_options from the end of the tuple
        if isinstance(tuple_rule[-1], dict):
            rule["options"] = tuple_rule.pop()

        # Extract value from front, if rule has a value
        if not is_binary:
            value = tuple_rule.pop(0)
        else:
            value = True
            if tuple_rule[0] == NEGATE:
                value = False
                tuple_rule = tuple_rule[1:]
        rule["value"] = value

        # Extract list of items from back, if rule has items
        service_condition = {}
        if is_service:
            service_condition = self._transform_item_list(tuple_rule.pop())

        # Rest is host list or tag list + host list
        host_condition = self._transform_host_conditions(tuple_rule)

        rule["condition"].update(service_condition)
        rule["condition"].update(host_condition)

        return rule

    def _transform_item_list(self, item_list):
        if item_list == ALL_SERVICES:
            return {}

        if not item_list:
            return {"service_description": []}

        sub_conditions = []

        # Assume WATO conforming rule where either *all* or *none* of the
        # host expressions are negated.
        # TODO: This is WATO specific. Should we handle this like base did before?
        negate = item_list[0].startswith("!")

        # Remove ALL_SERVICES from end of negated lists
        if negate and item_list[-1] == ALL_SERVICES[0]:
            item_list = item_list[:-1]

        # Construct list of all item conditions
        for check_item in item_list:
            if negate:
                if check_item[0] == '!':  # strip negate character
                    check_item = check_item[1:]
                else:
                    raise NotImplementedError(
                        "Mixed negate / not negated rule found but not supported")
            elif check_item[0] == '!':
                raise NotImplementedError("Mixed negate / not negated rule found but not supported")

            sub_conditions.append({"$regex": check_item})

        if negate:
            return {"service_description": {"$nor": sub_conditions}}
        return {"service_description": sub_conditions}

    def _transform_host_conditions(self, tuple_rule):
        if len(tuple_rule) == 1:
            host_tags = []
            host_list = tuple_rule[0]
        else:
            host_tags = tuple_rule[0]
            host_list = tuple_rule[1]

        condition = {}
        condition.update(self._transform_host_tags(host_tags))
        condition.update(self._transform_host_list(host_list))
        return condition

    def _transform_host_list(self, host_list):
        if host_list == ALL_HOSTS:
            return {}

        if not host_list:
            return {"host_name": []}

        sub_conditions = []

        # Assume WATO conforming rule where either *all* or *none* of the
        # host expressions are negated.
        # TODO: This is WATO specific. Should we handle this like base did before?
        negate = host_list[0].startswith("!")

        # Remove ALL_HOSTS from end of negated lists
        if negate and host_list[-1] == ALL_HOSTS[0]:
            host_list = host_list[:-1]

        # Construct list of all host item conditions
        for check_item in host_list:
            if check_item[0] == '!':  # strip negate character
                check_item = check_item[1:]

            if check_item[0] == '~':
                sub_conditions.append({"$regex": check_item[1:]})
                continue

            if check_item == CLUSTER_HOSTS[0]:
                raise MKGeneralException(
                    "Found a ruleset using CLUSTER_HOSTS as host condition. "
                    "This is not supported anymore. These rules can not be transformed "
                    "automatically to the new format. Please check out your configuration and "
                    "replace the rules in question.")
            if check_item == PHYSICAL_HOSTS[0]:
                raise MKGeneralException(
                    "Found a ruleset using PHYSICAL_HOSTS as host condition. "
                    "This is not supported anymore. These rules can not be transformed "
                    "automatically to the new format. Please check out your configuration and "
                    "replace the rules in question.")

            sub_conditions.append(check_item)

        if negate:
            return {"host_name": {"$nor": sub_conditions}}
        return {"host_name": sub_conditions}

    def _transform_host_tags(self, host_tags):
        if not host_tags:
            return {}

        conditions = {}
        tag_conditions = {}
        for tag_id in host_tags:
            # Folder is either not present (main folder) or in this format
            # "/abc/+" which matches on folder "abc" and all subfolders.
            if tag_id.startswith("/"):
                conditions["host_folder"] = tag_id.rstrip("+")
                continue

            negate = False
            if tag_id[0] == '!':
                tag_id = tag_id[1:]
                negate = True

            # Assume it's an aux tag in case there is a tag configured without known group
            tag_group_id = self._tag_groups.get(tag_id, tag_id)

            tag_conditions[tag_group_id] = {"$ne": tag_id} if negate else tag_id

        if tag_conditions:
            conditions["host_tags"] = tag_conditions

        return conditions


def get_tag_to_group_map(tag_config):
    """The old rules only have a list of tags and don't know anything about the
    tag groups they are coming from. Create a map based on the current tag config
    """
    tag_id_to_tag_group_id_map = {}

    for aux_tag in tag_config.aux_tag_list.get_tags():
        tag_id_to_tag_group_id_map[aux_tag.id] = aux_tag.id

    for tag_group in tag_config.tag_groups:
        for grouped_tag in tag_group.tags:
            tag_id_to_tag_group_id_map[grouped_tag.id] = tag_group.id
    return tag_id_to_tag_group_id_map
