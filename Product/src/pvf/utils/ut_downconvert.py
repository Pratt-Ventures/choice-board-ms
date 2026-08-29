# ut_downconvert.py
#
# excerpt from code used an external project at magicopt.com
#
# general constant / limit definitions
#
###############################################################################################################################################
#                                  This software and all derived works must contain this entire notice
# Copyright (c) 2015-2020 - MagicOpt, LLC, Virginia, USA and Pratt Ventures, LLC, Florida, USA
#    all rights reserved
#
#  This contents herein are provided from by MagicOpt, LLC of Virginia, US, and Pratt Ventures, LLC of Delaware, US.
#  This software is provided confidentially and licensed for use only in authorized contexts and
#  in conjunction with services of the firms.
#
#  No other use, distribution, or disclosure is permitted without express written consent.
#
#              This software and all derived works (which require consent) must contain this entire notice.
###############################################################################################################################################
#
#    last updated - July 2020
#
#   8/1/2020 - Added logic formerly in magicopt_tools, which is server focused, to reduce dependencies in the client only environment.

import datetime
import numpy as np

class downconvert_exception(Exception):
    """ general exception class, many others are a parameterized instance of this...
    """
    def __init__(self, *v_params, **kv_params):
        kv_list = []
        for k, v in kv_params.items():
            kv_list.append('{}={}'.format(k,v))
        self.message = format_key_value_to_str(*v_params, **kv_params)
        self.kv = kv_params

    def __str__(self):
        return repr(self.message)

def format_key_value_to_str(*v_params, **kv_params):
    """
    format a message in a string for  friendly-ish text message using text and keys provided.
    :param v_params: position params, added as values between ;
    :param kv_params: keyword params, added as key=value between ;
    :return:
    """
    kv_list = []
    for k, v in kv_params.items():
        kv_list.append('{}={}'.format(k,v))
    return '; '.join([*v_params] + kv_list)

def adjust_defaults_to_list_objects(arg_value):
    if isinstance(arg_value, str):
        arg_value = [arg_value]
    elif arg_value is None:
        arg_value = []
    return arg_value


def longest_prefix_match(prefix_match_list, string_to_check):
    if prefix_match_list is None or len(prefix_match_list) == 0:
        return -1
    match_len_list = [len(cur_prefix) if string_to_check.lower().startswith(cur_prefix.lower()) else 0 for cur_prefix in prefix_match_list]
    match_list_max = max(match_len_list)
    return match_list_max if match_list_max > 0 else -1

def DictTreeDownConverter(base_dict, *, include_fields=None, include_prefixes=None,
                          exclude_fields=None, exclude_prefixes=None):

    include_fields = adjust_defaults_to_list_objects(include_fields)
    include_prefixes = adjust_defaults_to_list_objects(include_prefixes)
    exclude_fields = adjust_defaults_to_list_objects(exclude_fields)
    exclude_prefixes = adjust_defaults_to_list_objects(exclude_prefixes)

    if len(include_fields) or len(include_prefixes):
        check_include = True
    else:
        check_include = False
    if len(exclude_fields) or len(exclude_prefixes):
        check_exclude = True
    else:
        check_exclude = False
    if isinstance(base_dict, (dict,)):
        _DictTreeDownConverter(base_dict, check_include, check_exclude, include_fields, include_prefixes,
                               exclude_fields, exclude_prefixes, key_path=[])
    elif isinstance(base_dict, (list,)):
        _ListTreeDownConverter(base_dict, check_include, check_exclude, include_fields, include_prefixes,
                               exclude_fields, exclude_prefixes, key_path=[])
    else:
        raise downconvert_exception('DictTreeDownConverter: unrecognized input type for conversion', base_dict_type=type(base_dict))
    return base_dict


def _DictTreeDownConverter(base_dict, check_include=False, check_exclude=False,
                           include_fields=None, include_prefixes=None,
                           exclude_fields=None, exclude_prefixes=None,
                           key_path=None):
    if key_path is None:
        key_path = []

    del_keys = []
    for k, v in base_dict.items():
        if not isinstance(k, (str, int, float, bool, type(None))):
            raise downconvert_exception('_DictTreeDownConverter: key is not str, int, float, or bool', key_path=key_path,
                                     found_type=type(k), found_value=str(k)[:50])
        if check_include:
            include_match_length = 1000 if k in include_fields else longest_prefix_match(include_prefixes, k)
        else:
            include_match_length = 1
        if check_exclude and include_match_length > 0:
            exclude_match_length = 1000 if k in exclude_fields else longest_prefix_match(exclude_prefixes, k)
            if exclude_match_length >= include_match_length:
                include_match_length = -1
        if include_match_length < 0:
            del_keys.append(k)
        else:
            if isinstance(v, (float, int, str, type(bool), type(None))):
                pass
            elif isinstance(v, (datetime.datetime,)):
                base_dict[k] = str(v)
            elif isinstance(v, (np.intc, np.int_, np.int32, np.int64)):
                base_dict[k] = int(v)
            elif isinstance(v, (np.float64,)):
                base_dict[k] = float(v)
            elif isinstance(v, np.ndarray):
                base_dict[k] = v.tolist()
            elif isinstance(v, tuple) and len(v) > 0:
                base_dict[k] = _ListTreeDownConverter(list(v), check_include, check_exclude, include_fields, include_prefixes,
                                       exclude_fields, exclude_prefixes, key_path=key_path + [k])
            elif isinstance(v, (list, type(list))):
                _ListTreeDownConverter(v, check_include, check_exclude, include_fields, include_prefixes,
                                   exclude_fields, exclude_prefixes, key_path=key_path + [k])
            elif isinstance(v, (dict,)):
                _DictTreeDownConverter(v, check_include, check_exclude, include_fields, include_prefixes,
                                       exclude_fields, exclude_prefixes, key_path=key_path + [k])
            elif key_path is not None:
                print('** IGNORED OBJECT in dict', key_path + [k], ' : type', type(v))
                base_dict[k] = 'unknown dict entry type - {}'.format(type(v))

    for k in del_keys:
        del base_dict[k]
    return base_dict


def _ListTreeDownConverter(base_list, check_include=False, check_exclude=False,
                           include_fields=None, include_prefixes=None,
                           exclude_fields=None, exclude_prefixes=None,
                           key_path=None):
    if key_path is None:
        key_path = []

    for list_index, v in enumerate(base_list):
        if isinstance(v, (float, int, str, type(bool), type(None))):
            pass
        elif isinstance(v, (np.intc, np.int_, np.int32, np.int64)):
            base_list[list_index] = int(v)
        elif isinstance(v, (np.float64,)):
            base_list[list_index] = float(v)
        elif isinstance(v, np.ndarray):
            base_list[list_index] = v.tolist()
        elif isinstance(v, (tuple,)) and len(v) > 0:
            base_list[list_index] = _ListTreeDownConverter(list(v), check_include, check_exclude, include_fields, include_prefixes,
                                       exclude_fields, exclude_prefixes, key_path=key_path + [list_index])

        elif isinstance(v, (list, type(list))):
            _ListTreeDownConverter(v, check_include, check_exclude, include_fields, include_prefixes,
                               exclude_fields, exclude_prefixes, key_path=key_path + [list_index])
        elif isinstance(v, (dict,)):
            _DictTreeDownConverter(v, check_include, check_exclude, include_fields, include_prefixes,
                                   exclude_fields, exclude_prefixes, key_path=key_path + [list_index])
        elif key_path is not None:
            print('** IGNORED OBJECT in list', key_path + [list_index], ' : type', type(v))
            base_list[list_index] = 'unknown list entry type - {}'.format(type(v))

    return base_list

