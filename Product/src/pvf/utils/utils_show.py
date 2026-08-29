# utils_show
# utilities to dump or show variables, structures, or objects
#
###############################################################################################################################################
#                                  This software and all derived works must contain this entire notice
# (c) 2017-2020 - Dan Hoogterp, Florida, USA
#    all rights reserved
#
#  This software is provided from the library of Dan Hoogterp and/or Pratt Ventures, a Delaware, US LLC, and is licensed in perpetuity
#  for use in the systems and contexts into which this software was explicitly incorporated by Dan Hoogterp or was explicitly authorized by
#  Dan Hoogterp and/or Pratt Ventures in writing.
#  The license include the right to use as provided or as derivative works within those contexts, providing the implementation and details
#  are not published, made public, redistributed, used in isolation, or used outside the context or scope of the original system.
#                                  This software and all derived works must contain this entire notice
###############################################################################################################################################
#
# version history
# 1.06- 9/19/2020 - Extracted from utils.py to reduce clutter and file size
#     - 9/21/2020 - utils becomes a master file that imports all sub-elements
#     - 11/22/2023 - corrected format_hierarchy issue that could fail if a 'None' key was discovered at the exact limit of nest levels.   
#     - 2/2024 - show_vars - added lines in multi-line mode have ..   prefix instead of repeating the date/timestamp.
#     - 2/2024 - removed np.int as it is no longer an alias for int in some versions of numpy

# import utils_general as ut
import numpy as np
import traceback
import inspect
import datetime
import time
import math
import random
import hashlib
import pickle
import gzip
import zipfile
import os
import sys
import copy
import socket
import string
# import requests
from statistics import mean
import json
import pandas as pd
from scipy.stats import chi2_contingency

# import utils_general as utg
# from numba.typed import List
# for the hatcher_score environment, patched to not depend on utils_general, only used .now() and utils_exception
_utils_show_version = "0.90"     # version string

class UtilsShow_Exception(Exception):
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


def now():
    """ simple method to retrieve text for current date/time
    """
    return '{:%m-%d %H:%M}'.format(datetime.datetime.now())


def assert_show(*argvalues, **arglist):
    show_vars(*argvalues, **arglist)
    return False

def show_vars(*argvalues, no_show=False, include_type=False, include_timestamp=True, semi_list=False, **arglist):    # show variables from parameter list
    if no_show:
        return
    show_time = now() + ': ' if include_timestamp else ''
    out_str = ''
    if argvalues is not None:
        for argv in argvalues:
            if len(out_str):
                if semi_list:
                    out_str += '; '
                else:
                    out_str += '\n{}'.format('...' + ' ' * (len(show_time) - 3))
            else:
                out_str = '{}'.format(show_time)
            out_str += '{}{}'.format('' if include_type is False else '({}) = '.format(type(argv)), argv)
    for k,v in arglist.items():
        if len(out_str):
            if semi_list:
                out_str += '; '
            else:
                out_str += '\n{}'.format('...' + ' ' * (len(show_time) - 3))
        else:
            out_str = '{}'.format(show_time)
        out_str += '{}{} = {}'.format(k,  '' if include_type is False else ' ({})'.format(type(v)), v)
    print(out_str)
    return


def show_vars_pass(*argvalues, **arglist):    # show variables from parameter list
    return


def show_vars_semi(*argvalues, include_type=False, include_timestamp=True, **arglist):
    if 'semi_list' not in arglist:
        return show_vars(*argvalues,
                         include_type=include_type,
                         include_timestamp=include_timestamp,
                         semi_list=True,
                         **arglist)
    return show_vars(*argvalues, include_type=include_type,
                     include_timestamp=include_timestamp,
                     **arglist)


def show_vars_semi_pass(*argvalues, **arglist):
    return

def show_dict(dump_it, title=None):
    if (title != None):
        print("\n{}".format(title))
    for k, v in dump_it.items():
        print('  {} : {}'.format(k, v))
    return

def get_abbrev_number_str(shorten_value, max_decimal_places=1, prefix='', suffix=''):
    assert 0 <= max_decimal_places <= 3, 'max_decimal_places must be between 0 and 3'

    if isinstance(shorten_value, (int,float, np.float32, np.float64, np.int32, np.int64)):
        if shorten_value > 1000000000:
            if max_decimal_places == 0:
                show_value = '{}{}G{}'.format(prefix, int(round(shorten_value / 1000000000, max_decimal_places)), suffix)
            else:
                show_value = '{}{}G{}'.format(prefix, round(shorten_value / 1000000000, max_decimal_places), suffix)
        elif shorten_value > 1000000:
            if max_decimal_places == 0:
                show_value = '{}{}M{}'.format(prefix, int(round(shorten_value / 1000000, max_decimal_places)), suffix)
            else:
                show_value = '{}{}M{}'.format(prefix, round(shorten_value / 1000000, max_decimal_places), suffix)
        elif shorten_value > 1000:
            if max_decimal_places == 0:
                show_value = '{}{}K{}'.format(prefix, int(round(shorten_value / 1000, max_decimal_places)), suffix)
            else:                
                show_value = '{}{}K{}'.format(prefix, round(shorten_value / 1000, max_decimal_places), suffix)
        else:
            if max_decimal_places == 0 or int(shorten_value) == shorten_value:
                show_value = '{}{}{}'.format(prefix, int(round(shorten_value, max_decimal_places)), suffix)
            else:
                show_value = '{}{}'.format(prefix, round(shorten_value, max_decimal_places))
    else:
        show_value = f'{prefix}{shorten_value}'

    return show_value


def get_obj_info(np_obj):
    class_info = str(type(np_obj))
    try:
        len_info = len(np_obj)
        len_info = f'len:{len_info}'
    except:
        len_info = ''
    try:
        size_info = sys.getsizeof(np_obj)
    except:
        size_info = 'getsizeof err'
    try:
        shape_info = np_obj.shape
        shape_info = f'shape:{shape_info}'
    except:
        shape_info = ''

    try:
        dtype_info = np_obj.dtype
        dtype_info = f'dtype:{dtype_info}'
    except:
        dtype_info = ''

    size_info = get_abbrev_number_str(size_info, max_decimal_places=1, prefix='size:', suffix='B')
    return ' '.join([class_info, dtype_info, len_info, shape_info, size_info])
   

def show_object(*objs, title=None, show_dir=False):
    stack = traceback.extract_stack()
    filename, lineno, function_name, code = stack[-2]

    if (title != None) :
        print("==================== ", title, " ====================")

    print("--- {0}:{1} {2}".format(filename, lineno, code))

    for o in objs :
        if show_dir :
            print("--- {0} Dir:{1}".format(type(o), dir(o)))

        o_dir = dir(o)
        for o_dir_entry in o_dir:
            if o_dir_entry[0] != '_':
                try :
                    show = getattr(o, o_dir_entry)
                except:
                    show = "    *** can't getattr".format(o_dir_entry)
                print('  {}={}'.format(o_dir_entry, show))

    if (title != None) : print ("========================================\n")

    return


def format_float_to_size(show_f_value, max_precision=6, max_significant=8, scientific_notation=True):
    if isinstance(show_f_value, (str, int, list)) or show_f_value in (None, 'na'):
        return '{}'.format(show_f_value)
    if show_f_value != 0:
        if scientific_notation is True and abs(show_f_value) < (.1 ** (max_precision - 1)):
            formatted_f_value = '{:+{precision}}'.format(show_f_value, precision='.{}e'.format(max(0, max_precision - 2)))
        elif scientific_notation is True and abs(show_f_value) > (10 ** (max_significant -1)):
            formatted_f_value = '{:+{precision}}'.format(show_f_value, precision='.{}e'.format(max(0, max_precision - 2)))
        else:
            exp_level = math.log(abs(show_f_value), 10)
            if exp_level > 0:
                mantissa = int(exp_level)
            else:
                mantissa = 0
            max_precision = min(max_precision, max_significant - 1 - mantissa)
            formatted_f_value = '{:{precision}}'.format(show_f_value, precision='.{}f'.format(max(0, max_precision)))
    else:
        mantissa = 0
        formatted_f_value = '0.0'
    return formatted_f_value


def clip_nested_data(clip_input, max_entries=-1, keep_keys=[], clip_keys=[]):
    if isinstance(clip_input, (list, str)):
        if max_entries <= 0:
            clip_output = clip_input
        else:
            clip_output = clip_input[:max_entries]
    elif isinstance(clip_input, (np.ndarray,)):
        if max_entries <= 0:
            clip_output = clip_input
        else:
            if len(np.ravel(clip_input)) > 2 * max_entries:
                clip_output = np.ravel(clip_input)[:max_entries]
            else:
                clip_output = clip_input
    elif isinstance(clip_input, (dict,)):
        clip_output = {}
        clip_counter = max_entries
        for k, v in clip_input.items():
            if clip_counter > 0:
                nested_data = clip_nested_data(v, max_entries)
                if isinstance(v, (dict, list, str)):
                    if len(nested_data) != len(v):
                        k += '_clip_rmv_{}'.format(len(v) - len(nested_data))
                clip_output[k] = nested_data
            elif clip_counter == 0:
                clip_output[k] = '... clipped - {} of {}'.format(max_entries, len(clip_input))
            if max_entries > 0:
                clip_counter -= 1
    else:
        clip_output = clip_input
    return copy.deepcopy(clip_output)


def show_truncated_string(full_string, max_to_display=100):
    if len(full_string) > max_to_display:
        midpoint = (max_to_display // 2) - 1
        full_string = full_string[:midpoint] + '...' + full_string[- midpoint:]
    return full_string


convert_open_ind = dict(tuple_type='(', list_type='[')
convert_close_ind = dict(tuple_type=')', list_type=']')
hidden_field_text = "[hidden]"

def convert_dict_to_3_columns_log(top_dict, *, max_show_str=500,
                                  column_titles=['Primary', 'SubKey', 'Contents'], sub_id_keys=[],
                                  max_list_condense_size=100, expand_nested_tuples=True,
                                  obscure_keys=[]):
    assert len(column_titles) == 3
    info_data_list = []
    for log_key, log_val in top_dict.items():
        if log_key in obscure_keys:
            sub_keys_and_values = {'': hidden_field_text}
        elif isinstance(log_val, dict):
            sub_keys_and_values = log_val
        elif isinstance(log_val, (list, tuple)):
            cur_ind_type = 'tuple_type' if isinstance(log_val, tuple) else 'list_type'
            if len(log_val) > 20 or sum([len(str(x))+5 for x in log_val]) > max_list_condense_size:
                sub_keys_and_values = {}
                for pos, list_member_val in enumerate(log_val):
                    sub_key = None
                    if isinstance(list_member_val, dict):
                        for sub_key_test in sub_id_keys:    # if a dict, we try to extra an 'id' type field to make it more friendly...
                            try:
                                sub_key = '{}{}{}:{}'.format(convert_open_ind[cur_ind_type], pos, convert_close_ind[cur_ind_type], list_member_val[sub_key_test])
                            except:
                                pass
                            if sub_key is not None:  # first defined sub_id key wins
                                break
                    if sub_key is None:
                        sub_key = '{}{}{}'.format(convert_open_ind[cur_ind_type], pos, convert_close_ind[cur_ind_type])
                    sub_keys_and_values[sub_key] = list_member_val
            else:
                sub_keys_and_values = {'{}0..{}{}'.format(convert_open_ind[cur_ind_type], len(log_val), convert_close_ind[cur_ind_type]):
                                           '{}{}{}'.format(convert_open_ind[cur_ind_type], ', '.join(log_val), convert_close_ind[cur_ind_type])}
        else:  # should be none or direct value
            sub_keys_and_values = {'': log_val}
        for sub_log_key, sub_log_val in sub_keys_and_values.items():
            if sub_log_key in obscure_keys:
                entry_contents = hidden_field_text
            else:
                entry_contents = format_hierarchy(sub_log_val, max_show_str=max_show_str,
                                                  obscure_keys=obscure_keys, expand_nested_tuples=expand_nested_tuples)
            entry_contents_rows = entry_contents.splitlines()
            for cur_entry_row in entry_contents_rows:
                info_data_list.append({column_titles[0]: log_key, column_titles[1]: sub_log_key, column_titles[2]: cur_entry_row.strip()})
    return info_data_list


def convert_dict_to_4_columns_log(top_dict, *, max_show_str=500,
                                  column_titles=['Primary', 'Subkey', 'SubSubKey', 'Contents'], sub_id_keys=[],
                                  max_list_condense_size=100, expand_nested_tuples=True,
                                  obscure_keys=[]):
    assert len(column_titles) == 4
    info_data_list = []
    for log_key, log_val in top_dict.items():
        if log_key in obscure_keys:
            sub_keys_and_values = {'': hidden_field_text}
        elif isinstance(log_val, dict):
            sub_keys_and_values = log_val
        elif isinstance(log_val, (list, tuple)):
            cur_ind_type = 'tuple_type' if isinstance(log_val, tuple) else 'list_type'
            if len(log_val) > 20 or sum([len(str(x))+5 for x in log_val]) > max_list_condense_size:
                sub_keys_and_values = {}
                for pos, list_member_val in enumerate(log_val):
                    sub_key = None
                    if isinstance(list_member_val, dict):
                        for sub_key_test in sub_id_keys:    # if a dict, we try to extra an 'id' type field to make it more friendly...
                            try:
                                sub_key = '{}{}{}:{}'.format(convert_open_ind[cur_ind_type], pos, convert_close_ind[cur_ind_type], list_member_val[sub_key_test])
                            except:
                                pass
                            if sub_key is not None:
                                break
                    if sub_key is None:
                        sub_key = '{}{}{}'.format(convert_open_ind[cur_ind_type], pos, convert_close_ind[cur_ind_type])
                    sub_keys_and_values[sub_key] = list_member_val
            else:
                sub_keys_and_values = {'{}0..{}{}'.format(convert_open_ind[cur_ind_type], len(log_val),convert_close_ind[cur_ind_type]):
                                           '{}{}{}'.format(convert_open_ind[cur_ind_type], ', '.join(log_val), convert_close_ind[cur_ind_type])}
        else:  # should be none or direct value
            sub_keys_and_values = {'': log_val}

        for sub_log_key, sub_log_val in sub_keys_and_values.items():
            if sub_log_key in obscure_keys:
                sub_sub_keys_and_values = {'': hidden_field_text}
            elif isinstance(sub_log_val, dict):
                sub_sub_keys_and_values = sub_log_val
            elif isinstance(sub_log_val, list):
                cur_ind_type = 'tuple_type' if isinstance(sub_log_val, tuple) else 'list_type'
                if len(sub_log_val) > 20 or sum([len(str(x))+5 for x in sub_log_val]) > max_list_condense_size:
                    sub_sub_keys_and_values = {}
                    for pos, list_member_val in enumerate(sub_log_val):
                        sub_sub_key = None
                        if isinstance(list_member_val, dict):
                            for sub_key_test in sub_id_keys:  # if a dict, we try to extra an 'id' type field to make it more friendly...
                                try:
                                    sub_sub_key = '{}{}{}:{}'.format(convert_open_ind[cur_ind_type], pos,
                                                                 convert_close_ind[cur_ind_type],
                                                                 list_member_val[sub_key_test])
                                except Exception as ex_info:
                                    pass
                                if sub_sub_key is not None:
                                    break
                        if sub_sub_key is None:
                            sub_sub_key = '{}{}{}'.format(convert_open_ind[cur_ind_type], pos,
                                                      convert_close_ind[cur_ind_type])
                        sub_sub_keys_and_values[sub_sub_key] = list_member_val
                else:
                    sub_sub_keys_and_values = {'{}0..{}{}'.format(convert_open_ind[cur_ind_type], len(sub_log_val),convert_close_ind[cur_ind_type]):
                                                   '{}{}{}'.format(convert_open_ind[cur_ind_type], ', '.join(sub_log_val), convert_close_ind[cur_ind_type])}
            else:  # should be none or direct value
                sub_sub_keys_and_values = {'': sub_log_val}

            for sub_sub_log_key, sub_sub_log_val in sub_sub_keys_and_values.items():
                if sub_sub_log_key in obscure_keys:
                    entry_contents = hidden_field_text
                else:
                    entry_contents = format_hierarchy(sub_sub_log_val, max_show_str=max_show_str,
                                                      obscure_keys=obscure_keys,
                                                      expand_nested_tuples=expand_nested_tuples)
                entry_contents_rows = entry_contents.splitlines()
                for cur_entry_row in entry_contents_rows:
                    info_data_list.append({column_titles[0]: log_key,
                                               column_titles[1]: sub_log_key,
                                               column_titles[2]: sub_sub_log_key,
                                               column_titles[3]: cur_entry_row.strip()})
    return info_data_list


def print_hierarchy_pass(*args, **kwargs):
    return


def print_hierarchy(*args, **kwargs):
    print(format_hierarchy(*args, **kwargs))
    return


def check_for_builtin(v):
    try:
        builtin_flag = inspect.isbuiltin(v)
        builtin_notes = ''
    except:
        builtin_flag = True
        builtin_notes = '?builtin-{}'.format(type(v))
    return builtin_flag, builtin_notes

atomic_types_and_tuple_list = (type(None), type, tuple, set, bool, int, np.int32, np.int64, np.uint, np.uint16, np.uint32, np.uint64, float, np.float16,np.float32, np.float64,
                               datetime.datetime, datetime.timedelta)
atomic_types_only_list = (type(None), type, bool, int, np.int32, np.int64, np.uint, np.uint16, np.uint32, np.uint64, float, np.float16,np.float32, np.float64,
                               datetime.datetime, datetime.timedelta)
general_sequence_type_list = (list, set, np.ndarray, pd.Series, tuple)

def format_hierarchy(*arg_contents, title=None, nest_level=None, indent_per_level=3, include_types=False,
                     max_show_str=80, max_to_display=250, expand_nested_tuples=False, expand_objects=True,
                     obscure_keys=None, skip_keys=None, skip_keys_containing=None, skip_keys_quietly=True, 
                     truncate_keys=None, show_first_member=None,
                     initial_nest_level=0, list_object_methods=True, key_cache=None,
                     **kwd_contents):

    if key_cache is None:
        key_cache = []

    if len(arg_contents) == 0 and len(kwd_contents) == 0:
        raise UtilsShow_Exception('format_hierarchy: no content detected, one or more positional or kw args expected, none received')

    if title is None:
        format_key = ''
    else:
        format_key = title

    if len(arg_contents):
        format_contents = list(arg_contents)
        if len(kwd_contents):
            format_contents.append(kwd_contents)
        if len(format_contents) == 1:
            format_contents = format_contents[0]
    else:
        format_contents = kwd_contents
        if len(format_contents) == 1:
            if title in (None, ''):
                format_key = list(format_contents)[0]
                format_contents = format_contents[format_key]

    if isinstance(skip_keys, str):
        skip_keys = [skip_keys]
    elif skip_keys is None:
        skip_keys = []

    if isinstance(skip_keys_containing, str):
        skip_keys_containing = [skip_keys_containing]
    elif skip_keys_containing is None:
        skip_keys_containing = []

    if isinstance(obscure_keys, str):
        obscure_keys = [obscure_keys]
    elif obscure_keys is None:
        obscure_keys = []

    if truncate_keys is None:
        truncate_keys = []

    if show_first_member is None:
        show_first_member = []

    nested_sequence_types = (list, set, np.ndarray, pd.Series, tuple)

    if initial_nest_level > 0:
        indent_str = ' ' * (initial_nest_level * indent_per_level)
    else:
        indent_str = ''

    if isinstance(format_contents, nested_sequence_types):
        return_str = _format_list(format_contents, format_key=format_key, nest_level=initial_nest_level, indent_per_level=indent_per_level,
                                  include_types=include_types, max_show_str=max_show_str, max_to_display=max_to_display,
                                  expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                  obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                  truncate_keys=truncate_keys, show_first_member=show_first_member,
                                  max_nest_level=nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
    elif isinstance(format_contents, dict):
        return_str = _format_dict(format_contents, format_key=format_key, nest_level=initial_nest_level, indent_per_level=indent_per_level,
                                  include_types=include_types, max_show_str=max_show_str, max_to_display=max_to_display,
                                  expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                  obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                  truncate_keys=truncate_keys, show_first_member=show_first_member,
                                  max_nest_level=nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
    elif isinstance(format_contents, str):
        return_str = _format_str(format_contents, format_key=format_key, nest_level=initial_nest_level,
                                 indent_per_level=indent_per_level,
                                 include_types=include_types, max_show_str=max_show_str, max_to_display=max_to_display,
                                 expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                 obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing,  skip_keys_quietly=skip_keys_quietly,
                                 truncate_keys=truncate_keys,
                                 show_first_member=show_first_member,
                                 max_nest_level=nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
    elif isinstance(format_contents, atomic_types_and_tuple_list):
        return_str = '{}{:20}{}: {}\n'.format(indent_str, format_key, '' if include_types is False else '{}'.format(type(format_contents)), format_contents)
    elif isinstance(format_contents, object) and not inspect.isbuiltin(format_contents) and expand_objects:
        return_str = _format_object(format_contents, format_key=format_key, nest_level=initial_nest_level, indent_per_level=indent_per_level,
                                             include_types=include_types, max_show_str=max_show_str,
                                             max_to_display=max_to_display,
                                         expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                             obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                             truncate_keys=truncate_keys, show_first_member=show_first_member,
                                    max_nest_level=nest_level, list_object_methods=list_object_methods, key_cache=key_cache)

    else:
        return_str = '{}{}{}: {}'.format(indent_str, format_key, '' if include_types is False else '{}'.format(type(format_contents)),format_contents)
    return return_str


def _format_str(format_contents, format_key=None, nest_level=0, indent_per_level=3,
                include_types=False, max_show_str=70,
                max_to_display=100, expand_nested_tuples=False, expand_objects=True,
                obscure_keys=[], skip_keys=[],  skip_keys_containing=[],  skip_keys_quietly=True,
                truncate_keys=[], show_first_member=[],
                max_nest_level=None, list_object_methods=True, key_cache=[]):
    if nest_level > 0:
        indent_str = ' ' * (nest_level * indent_per_level)
    else:
        indent_str = ''
    if format_key is None:
        format_key = 'str'
    if len(format_contents) > max_show_str:
        v = format_contents[:max_show_str // 2] + '...' + format_contents[- (max_show_str // 2):]
    else:
        v = format_contents
    return '{}{:20}{}: {}\n'.format(indent_str, format_key, '' if include_types is False else '{}'.format(type(format_contents)), v)


def _format_dict(format_contents, format_key=None, nest_level=0, indent_per_level=3, include_types=False,
                 max_show_str=70, max_to_display=100, expand_nested_tuples=False, expand_objects=True,
                 obscure_keys=[], skip_keys=[],  skip_keys_containing=[],  skip_keys_quietly=True,
                 truncate_keys=[], show_first_member=[],
                 max_nest_level=None, list_object_methods=True, key_cache=[]):
    if nest_level > 0:
        indent_str = ' ' * (nest_level * indent_per_level)
    else:
        indent_str = ''
    #indent_str = ' ' * ((nest_level + 1) * indent_per_level)

    if format_key is None or format_key == '':
        format_key = 'dict_{}'.format(nest_level)

    key_list = list(format_contents)
    eff_max_to_display = max_to_display
    if format_key in truncate_keys and len(key_list) > 6:
        eff_max_to_display = 6

    if format_key in show_first_member and len(key_list) > 1:
        eff_max_to_display = 1

    if len(skip_keys_containing) or len(skip_keys):
        new_key_list = [x for x in key_list if not (x in skip_keys or any([y in x for y in skip_keys_containing]))]
        skipped_field_count = len(key_list) - len(new_key_list)
        if skipped_field_count:
            key_list = new_key_list
    else:
        skipped_field_count = 0

    if len(key_list) > eff_max_to_display:
        truncate_index = max(1, eff_max_to_display // 2)
        truncate_start_key = key_list[truncate_index]
        new_key_list = key_list[:max(1, truncate_index)]
        if truncate_index > 1:
            new_key_list += key_list[- truncate_index:]
        key_list = new_key_list
        truncate_count = len(format_contents) - len(key_list)
        truncate_note = ' (truncated {{{}... <removed {}> ...{}}})'.format(truncate_index, truncate_count, eff_max_to_display // 2)
    else:
        truncate_start_key = ''
        truncate_note = ''
        truncate_index = -1
        truncate_count = 0

    if format_key is None:
        return_str = ''
    else:
        if nest_level > 0:
            return_str = '{}{}: {} {} dictionary {} items {} {} {}\n'.format(indent_str, format_key,
                                                                            '(' * nest_level, '{', len(format_contents), '}', ')' * nest_level,
                                                                             truncate_note)
        else:
            return_str = '{}{}: {} dictionary {} items {} {}\n'.format(indent_str, format_key,
                                                                            '{', len(format_contents), '}',
                                                                             truncate_note)

    # if skip_keys_containing:
    #    return_str += '_format_dict: skip_keys_containing: {}\n'.format(skip_keys_containing)

    nest_level += 1
    indent_str = ' ' * (nest_level * indent_per_level)
    nested_sequence_types = (list, np.ndarray, pd.Series, tuple) if expand_nested_tuples else (list, np.ndarray, pd.Series)

    for key_index, k in enumerate(key_list):
        if skipped_field_count > 0 and skip_keys_quietly is False and key_index == 0:
            return_str += '{}{:20}: <field instances not shown due to skip_keys[_containing] - {}>\n'.format(indent_str, '', skipped_field_count)
        if key_index == truncate_index:
            return_str += '{}{:20}: <truncated next {} dict values not shown>\n'.format(indent_str, truncate_start_key, truncate_count)
        v = format_contents[k]
        if k in skip_keys:
            pass
        elif k in obscure_keys:
            if isinstance(v, str) and len(v) > 12:
                return_str += '{}{:20}{}: {}..{}\n'.format(indent_str, k, '' if include_types is False else '{}'.format(type(v)), v[:3], v[-3:])
            else:
                return_str += '{}{:20}{}: <value not shown>\n'.format(indent_str, k, '' if include_types is False else '{}'.format(type(v)))
        elif isinstance(v, atomic_types_only_list):
            return_str += '{}{:20}{}: {}\n'.format(indent_str, k,'' if include_types is False else '{}'.format(type(v)), v)
        elif (max_nest_level is None and nest_level > 12) or max_nest_level is not None and nest_level > max_nest_level:
            if len(f'{v}') < 50:
                return_str += '{}{:20}{}: {} <nest level reached>\n'.format(indent_str, str(k),'' if include_types is False else '{}'.format(str(type(v))), v)
            else:
                return_str += '{}{:20}{}: <nest level reached - value not shown>\n'.format(indent_str, str(k), '' if include_types is False else type(v))
        elif isinstance(v, nested_sequence_types):
            return_str += _format_list(v, format_key=k, nest_level=nest_level, indent_per_level=indent_per_level,
                                       include_types=include_types, max_show_str=max_show_str,  max_to_display=max_to_display,
                                       expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                       obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing,  skip_keys_quietly=skip_keys_quietly,
                                       truncate_keys=truncate_keys, show_first_member=show_first_member,
                                       max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
        elif isinstance(v, dict):
            return_str += _format_dict(v, format_key=k, nest_level=nest_level, indent_per_level=indent_per_level,
                                       include_types=include_types, max_show_str=max_show_str,  max_to_display=max_to_display,
                                       expand_nested_tuples=expand_nested_tuples,  expand_objects=expand_objects,
                                       obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing,  skip_keys_quietly=skip_keys_quietly,
                                       truncate_keys=truncate_keys,
                                       show_first_member=show_first_member,
                                       max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
        elif isinstance(v, str):
            return_str += _format_str(v, format_key=k, nest_level=nest_level, indent_per_level=indent_per_level,
                                      include_types=include_types, max_show_str=max_show_str,
                                      max_to_display=max_to_display, expand_nested_tuples=expand_nested_tuples,
                                      obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing,  skip_keys_quietly=skip_keys_quietly,
                                      truncate_keys=truncate_keys,
                                      show_first_member=show_first_member,
                                      max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
        elif isinstance(v, atomic_types_and_tuple_list):
            return_str += '{}{:20}{}: {}\n'.format(indent_str, k,'' if include_types is False else '{}'.format(type(v)), v)
        elif isinstance(v, object) and not inspect.isbuiltin(v) and expand_objects:
            return_str += _format_object(v, format_key=k, nest_level=nest_level, indent_per_level=indent_per_level,
                                             include_types=include_types, max_show_str=max_show_str,
                                             max_to_display=max_to_display,
                                         expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                             obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                             truncate_keys=truncate_keys, show_first_member=show_first_member,
                                         max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
        else:
            return_str += '{}{:20}{}: {}\n'.format(indent_str, k, '' if include_types is False else '{}'.format(type(v)), v)
    return return_str


def _format_list(format_contents, format_key=None, nest_level=0, indent_per_level=3, include_types=False,
                 max_show_str=70, max_to_display=100, expand_nested_tuples=False, expand_objects=True,
                 obscure_keys=[], skip_keys=[],  skip_keys_containing=[],  skip_keys_quietly=True,
                 truncate_keys=[], show_first_member=[],
                 max_nest_level=None, list_object_methods=True, key_cache=[]):

    if format_key is None or format_key == '':
        format_key = 'list_{}'.format(nest_level)

    if nest_level > 0:
        indent_str = ' ' * (nest_level * indent_per_level)
    else:
        indent_str = ''

    if isinstance(format_contents, np.ndarray):
        type_note = 'np '
    elif isinstance(format_contents, pd.Series):
        type_note = 'pd '
    #elif isinstance(format_contents, List):
    #    type_note = 'List '
    else:
        type_note = ''

    try:
        key_list = list(format_contents)
    except:
        raise UtilsShow_Exception('_format_list: incorrect type received, non-iterable', format_contents=format_contents,
                              format_contents_type=type(format_contents))

    eff_max_to_display = max_to_display
    if format_key in truncate_keys:
        if len(key_list) > 6:
            eff_max_to_display = 6
        else:
            eff_max_to_display = max(2, len(key_list) // 2)

    if format_key in show_first_member and len(key_list) > 1:
        eff_max_to_display = 1

    if len(key_list) > eff_max_to_display:
        truncate_start_index = max(1, eff_max_to_display // 2)
        if eff_max_to_display > 1:
            truncate_end_index = len(key_list) - (eff_max_to_display // 2)
        else:
            truncate_end_index = len(key_list)

        truncate_count = truncate_end_index - truncate_start_index + 1
        truncate_key_note = ' tr{}..{}'.format(truncate_start_index, truncate_end_index)
        truncate_note = ' (truncated [{}... <removed {}> ...{}])'.format(truncate_start_index, truncate_count, len(key_list) - truncate_end_index)
        truncate_lower = truncate_start_index
        if eff_max_to_display > 1:
            truncate_upper = truncate_end_index - 1
        else:
            truncate_upper = len(key_list)
    else:
        truncate_lower = len(key_list)
        truncate_upper = -1
        truncate_key_note = ''
        truncate_note = ''
        truncate_start_index = -1
        truncate_count = 0

    nested_sequence_types = (list, np.ndarray, pd.Series, tuple) if expand_nested_tuples else (list, np.ndarray, pd.Series)
    special_handling = False
    total_length = 0
    for cur_index, v in enumerate(key_list):
        if cur_index < truncate_lower or cur_index > truncate_upper:
            if isinstance(v, str):
                element_length = len(v)
                if element_length > 8:  # a large number of small entries can be shown as a direct list...
                    total_length += len(v)
            elif isinstance(v, nested_sequence_types):
                if len(v) > 0:  # don't force enumeration of a list of empty lists or dicts
                    special_handling = True
            elif not isinstance(v, atomic_types_and_tuple_list) and not isinstance(v, general_sequence_type_list) and not isinstance(v, str):
                special_handling = True

    if total_length > 150:
        special_handling = True

    if special_handling is False:  # just show list, pretend no indent
        if truncate_start_index < 0:
            show_list_contents = format_contents
        else:
            show_list_contents = list(format_contents[:truncate_lower]) + [' ... '] + list(format_contents[truncate_upper:])
        return '{}{:20}{}: {}\n'.format(indent_str, format_key, '' if (include_types is False or len(format_contents) < 1) else '[0]{}'.format(type(format_contents[0])), show_list_contents)

    if format_key is None:
        return_str = ''
    else:
        if nest_level > 0:
            return_str = '{}{}: {} [ list {} items ] {}{} ]\n'.format(indent_str, format_key,
                                                                       '(' * nest_level, len(format_contents), ')' * nest_level,
                                                                      truncate_note)
        else:
            return_str = '{}{}: [ list {} items ]{}\n'.format(indent_str, format_key,
                                                                       len(format_contents),
                                                                      truncate_note)
        nest_level += 1
        indent_str = ' ' * (nest_level * indent_per_level)


    for cur_index, v in enumerate(key_list):
        cur_key = '{}[{}{}{}]{}'.format(format_key, type_note, cur_index, truncate_key_note, '' if include_types is False else '{}'.format(type(v)))
        if cur_index == truncate_start_index:
            cur_key = '{}[{}{}{}]'.format(format_key, type_note, cur_index, truncate_key_note)
            return_str += '{}{:20}: <truncated next {} list values not shown>\n'.format(indent_str, cur_key, truncate_count)
        if cur_index < truncate_lower or cur_index > truncate_upper:

            if isinstance(v, atomic_types_only_list):
                return_str += '{}{:20}: {}\n'.format(indent_str, cur_key, v)
            elif (max_nest_level is None and nest_level > 12) or max_nest_level is not None and nest_level > max_nest_level:
                if len(f'{v}') < 50:
                    return_str += '{}{:20}: {} <nest level reached>\n'.format(indent_str, str(cur_key), v)
                else:
                    return_str += '{}{:20}{}: <nest level reached - value not shown>\n'.format(indent_str, str(cur_key), '' if include_types is False else '{}'.format(type(v)))
            elif isinstance(v, nested_sequence_types):
                return_str += _format_list(v, format_key=cur_key, nest_level=nest_level, indent_per_level=indent_per_level,
                                           include_types=include_types, max_show_str=max_show_str,  max_to_display=max_to_display,
                                           expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                           obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing,  skip_keys_quietly=skip_keys_quietly,
                                           truncate_keys=truncate_keys,
                                           show_first_member=show_first_member,
                                           max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
            elif isinstance(v, dict):
                return_str += _format_dict(v, format_key=cur_key, nest_level=nest_level, indent_per_level=indent_per_level,
                                           include_types=include_types, max_show_str=max_show_str,  max_to_display=max_to_display,
                                           expand_nested_tuples=expand_nested_tuples,  expand_objects=expand_objects,
                                           obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing,  skip_keys_quietly=skip_keys_quietly,
                                           truncate_keys=truncate_keys, show_first_member=show_first_member,
                                           max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
            elif isinstance(v, str):
                return_str += _format_str(v, format_key=cur_key, nest_level=nest_level,
                                          indent_per_level=indent_per_level,
                                          include_types=include_types, max_show_str=max_show_str,
                                          max_to_display=max_to_display,
                                          expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                          obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                          truncate_keys=truncate_keys, show_first_member=show_first_member,
                                          max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
            elif isinstance(v, atomic_types_and_tuple_list):
                return_str += '{}{:20}: {}\n'.format(indent_str, cur_key, v)
            elif isinstance(v, object) and not inspect.isbuiltin(v) and expand_objects:
                return_str += _format_object(v, format_key=cur_key, nest_level=nest_level, indent_per_level=indent_per_level,
                                             include_types=include_types, max_show_str=max_show_str,
                                             max_to_display=max_to_display,
                                             expand_nested_tuples=expand_nested_tuples,  expand_objects=expand_objects,
                                             obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                             truncate_keys=truncate_keys, show_first_member=show_first_member,
                                             max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
            else:
                return_str += '{}{:20}: {}\n'.format(indent_str, cur_key, v)
    return return_str


def _format_object(format_object, format_key=None, nest_level=0, indent_per_level=3, include_types=False,
                 max_show_str=70, max_to_display=100, expand_nested_tuples=False, expand_objects=True,
                 obscure_keys=[], skip_keys=[], skip_keys_containing=[],  skip_keys_quietly=True, truncate_keys=[], show_first_member=[],
                 max_nest_level=None, list_object_methods=True, key_cache=None):

    if key_cache is None:
        key_cache = []

    if format_key is None or format_key == '':
        format_key = 'object_{}'.format(nest_level)


    if nest_level > 0:
        indent_str = ' ' * (nest_level * indent_per_level)
    else:
        indent_str = ''
    #indent_str = ' ' * ((nest_level + 1) * indent_per_level)

    # convert object to a filtered dictionary...
    format_contents = {}
    method_list = []
    for k in dir(format_object):
        if k[0] != '_':
            try:
                v = getattr(format_object, k)
            except Exception as ex_info:
                v = " ** type unobtainium - {} **".format(ex_info)
            if not inspect.isroutine(v):
                format_contents[k] = v
            elif list_object_methods:
                method_list.append(k)
    if len(method_list):
        format_contents['_method_list'] = ', '.join(method_list)

    object_contents_key = hashlib.sha224(str(format_contents).encode('utf-8')).hexdigest()[0:20]
    # first we assess if something was seen before by _format_object and politely exclude if so....
    try:
        if object_contents_key in key_cache:
            if nest_level > 0:
                return_str = '{}{}: {} {} object already seen {}:{} - {} items {} {}\n'.format(indent_str, format_key,
                                                                '(' * nest_level, '{', type(format_object), object_contents_key,
                                                                                               len(format_contents), '}', ')' * nest_level)
            else:
                return_str = '{}{}: {} object already seen {}:{} - {} items {}\n'.format(indent_str, format_key,
                                                                                '{', type(format_object), object_contents_key,
                                                                                         len(format_contents), '}')
            return return_str
    except:
        return_str = '{}{}: {} data type for object {} type not understood - {} items {}\n'.format(indent_str, format_key,
                                                                                 '{', object_contents_key,
                                                                                 len(format_contents), '}')
        return return_str
    key_cache.append(object_contents_key)   # stop cycles...

    key_list = list(format_contents)
    eff_max_to_display = max_to_display
    if format_key in truncate_keys and len(key_list) > 6:
        eff_max_to_display = 6

    if format_key in show_first_member and len(key_list) > 1:
        eff_max_to_display = 1

    if len(skip_keys_containing) or len(skip_keys):
        new_key_list = [x for x in key_list if not (x in skip_keys or any([y in x for y in skip_keys_containing]))]
        skipped_field_count = len(key_list) - len(new_key_list)
        if skipped_field_count:
            key_list = new_key_list
    else:
        skipped_field_count = 0

    if len(key_list) > eff_max_to_display:
        truncate_index = max(1, eff_max_to_display // 2)
        truncate_start_key = key_list[truncate_index]
        new_key_list = key_list[:max(1,truncate_index)]
        if truncate_index > 1:
            new_key_list += key_list[- truncate_index:]
        key_list = new_key_list
        truncate_count = len(format_contents) - len(key_list)
        truncate_note = ' (truncated {{{}... <removed {}> ...{}}})'.format(truncate_index, truncate_count, eff_max_to_display // 2)
    else:
        truncate_start_key = ''
        truncate_note = ''
        truncate_index = -1
        truncate_count = 0


    if format_key is None:
        return_str = ''
    else:
        if nest_level > 0:
            return_str = '{}{}: {} {} object {} - {} items {} {} {}\n'.format(indent_str, format_key,
                                                            '(' * nest_level, '{', type(format_object), len(format_contents), '}', ')' * nest_level,
                                                                             truncate_note)
        else:
            return_str = '{}{}: {} object {} - {} items {} {}\n'.format(indent_str, format_key,
                                                                            '{', type(format_object), len(format_contents), '}',
                                                                             truncate_note)
    nest_level += 1
    indent_str = ' ' * (nest_level * indent_per_level)
    nested_sequence_types = (list, type(list), np.ndarray, pd.Series, tuple) if expand_nested_tuples else (list, type(list), np.ndarray, pd.Series)

    for key_index, k in enumerate(key_list):
        if skipped_field_count > 0 and skip_keys_quietly is False and key_index == 0:
            return_str += '{}{:20}: <field instances not shown due to skip_keys[_containing] - {}>\n'.format(indent_str, '', skipped_field_count)
        if key_index == truncate_index:
            return_str += '{}{:20}: <truncated next {} dict values not shown>\n'.format(indent_str, truncate_start_key, truncate_count)
        v = format_contents[k]
        if k in skip_keys:
            pass
        elif any([x in k for x in skip_keys_containing]):
            pass
        elif k in obscure_keys:
            if isinstance(v, str) and len(v) > 12:
                return_str += '{}{:20}{}: {}..{}\n'.format(indent_str, str(k), '' if include_types is False else '{}'.format(type(v)), v[:3], v[-3:])
            else:
                return_str += '{}{:20}{}: <value not shown>\n'.format(indent_str, str(k), '' if include_types is False else '{}'.format(type(v)))
        elif isinstance(v, atomic_types_only_list):
                return_str += '{}{:20}{}: {}\n'.format(indent_str, k,'' if include_types is False else '{}'.format(type(v)), v)
        elif (max_nest_level is None and nest_level > 12) or max_nest_level is not None and nest_level > max_nest_level:
            if len(f'{v}') < 50:
                return_str += '{}{:20}{}: {} <nest level reached>\n'.format(indent_str, k,'' if include_types is False else '{}'.format(type(v)), v)
            else:
                return_str += '{}{:20}{}: <nest level reached - value not shown>\n'.format(indent_str, k, '' if include_types is False else '{}'.format(type(v)))
        elif isinstance(v, atomic_types_and_tuple_list):
            return_str += '{}{:20}{}: {}\n'.format(indent_str, k,'' if include_types is False else '{}'.format(type(v)), v)
        elif isinstance(v, nested_sequence_types):
            return_str += _format_list(v, format_key=k, nest_level=nest_level, indent_per_level=indent_per_level,
                                       include_types=include_types, max_show_str=max_show_str,  max_to_display=max_to_display,
                                       expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                       obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                         truncate_keys=truncate_keys, show_first_member=show_first_member,
                                       max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
        elif isinstance(v, dict):
            return_str += _format_dict(v, format_key=k, nest_level=nest_level, indent_per_level=indent_per_level,
                                       include_types=include_types, max_show_str=max_show_str,  max_to_display=max_to_display,
                                       expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                       obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                         truncate_keys=truncate_keys,
                                       show_first_member=show_first_member,
                                       max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
        elif isinstance(v, str):
            return_str += _format_str(v, format_key=k, nest_level=nest_level, indent_per_level=indent_per_level,
                                      include_types=include_types, max_show_str=max_show_str,
                                      max_to_display=max_to_display,
                                      expand_nested_tuples=expand_nested_tuples, expand_objects=expand_objects,
                                      obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                        truncate_keys=truncate_keys,
                                      show_first_member=show_first_member,
                                      max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
        else:
            builtin_flag, builtin_msg = check_for_builtin(v)
            if builtin_msg != '':
                return_str += '{}{:20}{}: {}\n'.format(indent_str, k, '', builtin_msg)
            elif isinstance(v, object) and not builtin_flag and expand_objects:
                return_str += _format_object(v, format_key=k, nest_level=nest_level, indent_per_level=indent_per_level,
                                          include_types=include_types, max_show_str=max_show_str,
                                          max_to_display=max_to_display,
                                             expand_nested_tuples=expand_nested_tuples,  expand_objects=expand_objects,
                                          obscure_keys=obscure_keys, skip_keys=skip_keys, skip_keys_containing=skip_keys_containing, skip_keys_quietly=skip_keys_quietly,
                                            truncate_keys=truncate_keys,
                                          show_first_member=show_first_member,
                                             max_nest_level=max_nest_level, list_object_methods=list_object_methods, key_cache=key_cache)
            else:
                return_str += '{}{:20}{}: {}\n'.format(indent_str, k, '' if include_types is False else '{}'.format(type(v)), v)
    return return_str

