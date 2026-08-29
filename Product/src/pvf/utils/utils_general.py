# utils_general
# defines general utils capability - exception, open/close files with retry
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
# 0.9 - 9/21/2020 - isolated from utils to reduce clutter in the utils.py file.
#     - 10/28/2022- drop columns before renames in load_file_to_dataframe.
#     - 10/29/2022- load_to_dataframe caching now adds the base file _ext to the file name
#     - 12/17/2022- change from .save to .close in xlsx writer output
#     - 3/07/2024 - fixed missing definition of max_io_retry in try_listdir
#     - 6/25/2024 - added .tar.gz as an input file type in load_file_to_dataframe (detected as zip file)
#     -11/20/2024 - added support for sheet=None to retrieve all sheets in load_file_to_dataframe
#     -12/09/20234- cloudpickle support deprecated for obvious reasons.

_utils_general_version = 0.91

import numpy as np
import traceback
import inspect
import datetime
import time
import math
import random
import hashlib
import pickle
cloudpickle = None
import gzip
import zipfile
import tarfile
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
import importlib
import base64

from ..config.pvf_config_settings import pvf_settings as settings

# from numba.typed import List
# import utils_show as uts

class Utils_Exception(Exception):
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


def now():
    """ simple method to retrieve text for current date/time
    """
    return '{:%m-%d %H:%M}'.format(datetime.datetime.now())


def now_ymd():
    """ simple method to retrieve text for current date/time with full y/m/d
    """
    return '{:%y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())


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


def nan_check(np_array: np.ndarray):
    """ nan_check - check for nan values in a numpy array
    :param np_array: numpy array to check for nan values
    :return: True if nan values are found, False if no nan values are found
    """
    return np.isnan(np_array).any()

def conditional_import(import_name):
    try:
        import_module_object = importlib.import_module(import_name)
    except Exception as ex_info:
        if isinstance(ex_info, ModuleNotFoundError):
            import_module_object = None
        else:
            raise Utils_Exception('utils.conditional_import exception', import_name=import_name, exception=ex_info)
    return import_module_object


def get_hex_hash_from_args(*arg_list, hash_length=20, **kw_list):
    # WARNING - this is passed down as a tuple, so equivalently rendered data might differ (e.g., int vs str of an int)
    key_str = key_concat(arg_list)   # likely should be *arg_list, but that will break all extant hash values
    if kw_list:  # note - this is existing key order dependent; written when dicts were always sorted...
        key_str = key_concat(kw_list.keys(), input_str=key_str)
        key_str = key_concat(kw_list.values(), input_str=key_str)
    hex_key = hashlib.sha224(key_str.encode('utf-8')).hexdigest()[0:hash_length]
    return hex_key

def parse_activation_string(activation_code: str):
    token = customer_name = admin_name = customer_email = expiration_time_str = make_strings_better = None
    try:    
        if activation_code not in ("", None):
            package_clear = base64.urlsafe_b64decode(activation_code.encode('ascii')).decode('ascii')
            activation_parts = package_clear.split('|')
        else:
            activation_parts = []
        if len(activation_parts) == 6:
            token = activation_parts[0]
            customer_name = activation_parts[1]
            admin_name = activation_parts[2]
            customer_email = activation_parts[3]
            expiration_time_str = activation_parts[4]
            expiration_time = int(expiration_time_str)
            make_strings_better = activation_parts[5]
    except Exception as ex_info:
        raise ex_info
    return token, customer_name, admin_name, customer_email, expiration_time, make_strings_better

def make_activation_string(*, customer_name, admin_name, customer_email, expiration_time: int=None, expiration_duration_secs: int=7*24*3600, make_strings_better: int=None) -> list[str, str]:
    if make_strings_better is None:
        make_strings_better = np.random.randint(10000,99999)    # unique cookies are much better - doesn't add security
    if expiration_time is None:
        expiration_time = int(time.time() + expiration_duration_secs)
    expected_token = get_hex_hash_from_args(settings.ACCOUNT_ACTIVATION_TOKEN_KEY, customer_name, admin_name, customer_email, expiration_time, str(make_strings_better), settings.ACCOUNT_ACTIVATION_TOKEN_KEY)
    clear_payload = f"{expected_token}|{customer_name}|{admin_name}|{customer_email}|{expiration_time}|{make_strings_better}"
    encoded_payload = base64.urlsafe_b64encode(clear_payload.encode("ascii")).decode('ascii')
    return expected_token, encoded_payload


def key_concat(*arg_list, delim=':', input_str=None):
    """ key_concat - concatenate an arbitrary list and format into a hashable string based on positional args
    """
    key_str = input_str if input_str else ""

    for el in arg_list :
        if (delim != None and len(key_str) > 0) : key_str += "{}{}".format(delim, el)
        else: key_str += "{}".format(el)

    return key_str

def filter_string_for_filesystem(raw_str, max_length=80):
    return raw_str.replace('.', '_').replace('\\', '_').replace('/', '_').replace("'", "_").replace('"', '_').replace("@","_").replace(":", "_")[:max_length]

def filter_string_for_sql_safety(raw_str, max_length=80):
    return raw_str.replace("'", '_').replace('"', '_').replace('/', '_').replace("\\", "_").replace(".", "_")[:max_length]

class MapList(list):
    def map(self, fctn):
        """ map() in this context executes the map and returns a MapList, rather than a map object.
        """
        return MapList(map(fctn, self))


class LockedClass:
    """
    This class provides an attribute locked class.  No new attributes can be created while locked.
    The init function's last step is to call _lock(), which leaves the external view in locked state.
    Method invocations that may create new attributes would use _unlock() and _lock() at entry/exit
    to allow recursive attribute use internally.
    Otherwise, the derived class is normal in other respects.
    """
    def __init__(self, *v_params, **kv_params):
        """
        default initializer sets named attribute to each corresponding value from key/value parameters
        :param v_params: positional params - must be empty
        :param kv_params: key-value params, copied to attributes when present
        """
        if len(v_params) > 0:
            raise Utils_Exception('LockedClass__init__: unexpected positional parameters',
                              v_params=v_params, kv_params=kv_params)
        self._insert(**kv_params)
        self._lock()
        return

    def _lock(self):
        if '_LockedClass__lock_state' not in self.__dict__ :
            self.__lock_state = 1    # note - accessing superclass variable, _LockedClass__lock_state
            # self.__dict__['__lock_state'] = 1
        else:
            self.__lock_state += 1
        return self

    def _unlock(self):
        if '_LockedClass__lock_state' not in self.__dict__ :
            self.__lock_state = 0
        else:
            self.__lock_state -= 1
        return self

    def _insert(self, **kv_params):
        """
        inserts all keys as attributes with corresponding value, ignores lock state, but does not change it.
        :param kv_params:
        :return:
        """
        for key, value in kv_params.items():
            self.__dict__[key] = value
        return

    def __setattr__(self, key, value):
        """
        setting an attribute -- existing keys always allowed, new keys prohibited when locks are active.
        :param key:
        :param value:
        :return:
        """
        if key in self.__dict__ or '_LockedClass__lock_state' not in self.__dict__ or self.__lock_state <= 0:
            self.__dict__[key] = value
            return
            # return super(LockedClass, self).__setattr__(key, value)
        error_message_kws = format_key_value_to_str(lock_count=self.__lock_state, object_type=type(self))
        raise AttributeError('LockedClass: attribute "{}" does not exist while locked; {}'.format(key, error_message_kws))


def DictObjectTemplate(*lock_with_allowed_additions, LOCK_KEYS=False, **allowed_keys_with_defaults):
    """
    :param allowed_keys: From positional args, each becomes an allowed, but not mandatory, key value.
    The presence of one or more 'allowed_keys' indicates that arbitrary added keys are not allowed.
    Use 'None' or similar placeholder if no explicit added keys are identified, but the key set should be locked at
    the default set.
    :param allowed_keys_with_defaults: From a set of key=value pairs, each becomes an allowed key with value as default/initial value
    :return:

    example:
            word_entry_template = ut.DictObjectTemplate(LOCK_KEYS=True,
                                                            word_text=None,
                                                            word_position=-1,
                                                            start_sentence_position=-1,
                                                            end_sentence_position=-1,
                                                            )
        then word_entry_template(word_text='word', word_position=7)  # creates entity (subclassed dict) with two explicits and two defaults, new keys prohibited
    """
    new_dict_object = DictObject(allowed_keys_with_defaults)
    if lock_with_allowed_additions is not None and len(lock_with_allowed_additions) > 0:
        if len(lock_with_allowed_additions) == 1 and not isinstance(lock_with_allowed_additions, (list, tuple)):
            lock_with_allowed_additions = lock_with_allowed_additions[0]
        new_dict_object._allowed_keys = tuple(lock_with_allowed_additions)
    elif LOCK_KEYS is True:
        new_dict_object._allowed_keys = ['__no_additional_keys_allowed_']
    return new_dict_object._copy_insert


class DictObject(dict):
    """
    make an object that is a dictionary with object like attribute set/get ability for existing dictionary contents
    This is mainly for static configuration objects, where object-like syntax is preferable to dictionary and configuration
    errors can be caught early by configuring default or allowed values.
    Warning: Attributes (obj.attr) can be used as a synonym for obj['attr'] where the attr is a valid attribute name and does not
    conflict with standard dict object attributes.
    New key values can be created with dictionary syntax, possibly limited by the _allowed fields list (those specified without a default value).
    New key values and attributes cannot be created with attribute (obj.attr) syntax.  obj._supersetattr() can be used to set
    new attribute values, but is not recommended.
    """
    def __init__(self, *args, **kwds):
        super(DictObject, self).__setattr__('_allowed_keys', None)
        super(DictObject, self).__init__(*args, **kwds)
        return

    def __getattr__(self, key):
        """
        request to retrieve an unknown attribute from the object, so we return primary dict member by key if available.
        :param key:
        :return: value associated with key in dict or raises attribute error
        """
        if key in self.__dict__:
            return super(DictObject, self).__getattr__(key)

        if key not in self:
            raise AttributeError('DictObject: key "{}" not found'.format(key))

        if False and self._allowed_keys is not None and key not in self and key not in self._allowed_keys:
            raise AttributeError('DictObject: key "{}" not found'.format(key))
        if False and key not in self:  # still hacking at this, not pickling properly right now...
            return super(DictObject, self).__getattr__(key)

        return self[key]

    def __setattr__(self, key, value):
        """
        setting an attribute -- existing or allowed keys in dict are updated.
        Otherwise, the attribute must already exist for this object, or an AttributeError is raised.
        :param key:
        :param value:
        :return:
        """
        if key in self.__dict__ or key in['_allowed_keys']:
            return super(DictObject, self).__setattr__(key, value)
        if key not in self and key not in self._allowed_keys:
            raise AttributeError('DictObject: key "{}" not found'.format(key))
        self[key] = value
        return

    def _supersetattr(self, key, value):
        """
        setting an attribute -- existing or allowed keys in dict are updated.
        Otherwise, the attribute must already exist for this object, or an AttributeError is raised.
        :param key:
        :param value:
        :return:
        """
        return super(DictObject, self).__setattr__(key, value)

    def __delattr__(self, key):
        if key in self.__dict__[key]:
            super(DictObject, self).__delattr__(key)
        if key not in self:
            raise AttributeError('DictObject: key "{}" not found'.format(key))
        del self[key]
        return

    def __setitem__(self, key, value):
        #print('__setitem__ key {} value {}  self._allowed_keys {}  self {}'.format(key, value, self._allowed_keys, self))
        if '_allowed_keys' not in self.__dict__ or self._allowed_keys is None or key in self._allowed_keys or key in self:
            return super(DictObject, self).__setitem__(key, value)
        raise KeyError('DictObject: key "{}" does not exist and is not in allowed_keys for this object'.format(key))

    def _copy_insert(self, *singleton_entries, **insert_entries):
        if len(singleton_entries) > 0:
            raise KeyError('DictObject: dict-like key=value pairs expected, one or more keys / values are missing; invalid_key_value_pairs={}'.format(singleton_entries))
        new_dict_object = DictObject()
        for k in self:
            if k in insert_entries:
                new_dict_object[k] = insert_entries[k]
            else:
                new_dict_object[k] = copy.copy(self[k])

        invalid_keys = []
        for key in insert_entries:
            if key not in new_dict_object:
                if self._allowed_keys is None or key in self._allowed_keys:
                    new_dict_object[key] = insert_entries[key]
                else:
                    invalid_keys.append(key)
        if len(invalid_keys):
            raise KeyError('DictObject: key(s) "{}" not in allowed_keys or default keys for this object'.format(", ".join(invalid_keys)))
        new_dict_object._allowed_keys = copy.copy(self._allowed_keys)
        return new_dict_object

    def __deepcopy__(self, memo):
        new_dict_object = DictObject()
        for key in self:
            new_dict_object[key] = copy.deepcopy(self[key], memo)
        new_dict_object._allowed_keys = copy.copy(self._allowed_keys)
        return new_dict_object


def get_dict_value(check_dict, key_value, *, default_value=None, delete_key=False):
    """
    get_dict_value - return a key from a dictionary, with optional default processing, with optional delete after extract processing
    :param check_dict: dictionary to check for values in
    :param key_value: key to look for
    :param default_value: value to return if key is not found
    :param delete_key: boolean to indicate if key should be deleted in place if found
    :return:
    """
    if isinstance(key_value, (list, tuple)):
        cur_dict = check_dict
        for cur_key_value in key_value[:-1]:
            if cur_key_value in cur_dict and isinstance(cur_dict[cur_key_value], dict):
                cur_dict = cur_dict[cur_key_value]
            else:
                return default_value
        if key_value[-1] in cur_dict:
            return cur_dict[key_value[-1]]
        else:
            return default_value
    else:
        if key_value in check_dict:
            return_value = check_dict[key_value]
            if delete_key:
                del check_dict[key_value]
        else:
            return_value = default_value
    return return_value


class QuickCount:
    def __init__(self, first_value=0):
        self.prior_value = first_value - 1
        self.issued = 0
        return

    @property
    def next(self):
        self.prior_value += 1
        self.issued += 1
        return self.prior_value

    @property
    def next_str(self):
        self.prior_value += 1
        self.issued += 1
        return str(self.prior_value)

    def prior(self):
        return self.prior_value


class MeanTracker:
    def __init__(self, preload_mean=0.0, preload_count=0, preload_list=None, init_hook=None):
        if preload_mean != 0.0 and preload_count == 0:
            # we default preload_count to 3 if a non-zero mean is specified for legacy compatibility
            preload_count = 3
        self.preload_total = preload_mean * preload_count
        self.preload_count = preload_count
        self._total = 0
        self._count = 0
        self.related_mean_tracker = None
        self.related_count_tracker = None
        self.related_total_tracker = None
        self.related_min_tracker = None
        self.related_max_tracker = None

        if preload_count > 0:
            self._max = preload_mean
            self._min = preload_mean
        else:
            self._max = None
            self._min = None
        if preload_list is not None:
            self.preload_total += sum(preload_list)
            self.preload_count += len(preload_list)
        if init_hook is not None:
            init_hook(self)
        return

    def add(self, add_value):
        self._total += add_value
        self._count += 1
        if self._min is None or add_value < self._min:
            self._min = add_value
        if self._max is None or add_value > self._max:
            self._max = add_value
        return

    def clear(self, add_value):
        self._total = 0
        self._count = 0
        return

    def set_related_tracker_all(self, tracker_like):
        self.related_mean_tracker = tracker_like
        self.related_count_tracker = tracker_like
        self.related_total_tracker = tracker_like
        self.related_min_tracker = tracker_like
        self.related_max_tracker = tracker_like

        return

    def set_related_tracker_mean(self, tracker_like):
        self.related_mean_tracker = tracker_like
        return
    def set_related_tracker_count(self, tracker_like):
        self.related_count_tracker = tracker_like
        return
    def set_related_tracker_total(self, tracker_like):
        self.related_total_tracker = tracker_like
        return
    def set_related_tracker_min(self, tracker_like):
        self.related_min_tracker = tracker_like
        return
    def set_related_tracker_max(self, tracker_like):
        self.related_max_tracker = tracker_like
        return

    mean = property(lambda self: 0 if self._count + self.preload_count == 0 else (self._total + self.preload_total) / (self._count + self.preload_count) )
    count = property(lambda self: self._count)
    total = property(lambda self: self._total)
    min = property(lambda self: self._min)
    max = property(lambda self: self._max)
    related_mean_percentage = property(lambda self: round(100.0 * self.mean / self.related_mean_tracker.mean, 1) if self.related_mean_tracker is not None and self.related_mean_tracker.mean != 0 else None)
    related_count_percentage = property(lambda self: round(100.0 * self.count / self.related_count_tracker.count, 1) if self.related_count_tracker is not None and self.related_count_tracker.count != 0 else None)
    related_total_percentage = property(lambda self: round(100.0 * self.total / self.related_total_tracker.total, 1) if self.related_total_tracker is not None  and self.related_total_tracker.total != 0 else None)
    related_min_percentage = property(lambda self: round(100.0 * self.min / self.related_min_tracker.min, 1) if self.related_min_tracker is not None  and self.related_min_tracker.min != 0 else None)
    related_max_percentage = property(lambda self: round(100.0 * self.max / self.related_max_tracker.max, 1) if self.related_max_tracker is not None  and self.related_max_tracker.max != 0 else None)

class TimeTracker(dict):
    def __init__(self, category=None, value_mode='seconds', default_category='unspecified', track_default=True, total_category='total',
                 track_total=True, round_digits=2):
        self.default_category = default_category
        self.track_default = track_default
        self.total_category = total_category
        self.track_total = track_total
        value_mode_options = dict(seconds=1.0, s=1.0, minutes=60.0, min=60.0, hours=3600.0, h=3600.0, milliseconds=0.001, milli=0.001)
        if value_mode not in value_mode_options:
            raise Utils_Exception('TimeTracker: value_mode is not recognized', value_mode=value_mode, allowed_value_modes=', '.join(list(value_mode_options)))
        self.value_mode = value_mode
        self.value_divisor = value_mode_options[value_mode]
        self.round_digits = round_digits

        self.start_time = time.time()
        self.checkpoint_time = self.start_time
        self.counts = {}
        self.time_accum = {}
        self.current_category = self.default_category if category in [None, ''] else category
        if self.current_category != self.default_category or track_default is True:
            self.time_accum[self.current_category] = 0.0
            self.counts[self.current_category] = 1
        self.previous_bucket_history = []
        self._update_dict_view()
        return

    def _update_dict_view(self):
        self.clear()
        for k, v in self.time_accum.items():
            self[k] = round(v, self.round_digits)
        if self.track_total:
            self[self.total_category] = round((self.checkpoint_time - self.start_time) / self.value_divisor, self.round_digits)
        return self

    def pop(self):
        if len(self.previous_bucket_history) > 1:
            new_category = self.previous_bucket_history[-2]
            self.previous_bucket_history = self.previous_bucket_history[:-2]
        else:
            new_category = None
        return self.update(new_category)

    def update(self, category=None, reset=True):
        try:
            new_checkpoint_time = time.time()
            if self.current_category != self.default_category or self.track_default is True:
                self.time_accum[self.current_category] += (new_checkpoint_time - self.checkpoint_time) / self.value_divisor
            self.checkpoint_time = new_checkpoint_time
            if category not in [None, '']:
                new_category = category
            elif reset:
                new_category = self.default_category
            else:
                new_category = self.current_category

            if new_category != self.current_category:
                self.previous_bucket_history.append(self.current_category)
                self.previous_bucket_history = self.previous_bucket_history[-10:]
                if new_category != self.default_category or self.track_default is True:
                    if new_category not in self:
                        self.time_accum[new_category] = 0.0
                        self.counts[new_category] = 0
                    self.counts[new_category] += 1

            self.current_category = new_category
        except:
            # print_hierarchy(time_track_update_failed=self, update_category=category, update_reset=reset)
            raise
        return self._update_dict_view()

    def merge_categories(self, merge_dict_or_list):
        if isinstance(merge_dict_or_list, list):
            for k in merge_dict_or_list:
                if k not in self:
                    self.time_accum[k] = 0.0
                    self.counts[k] = 0
        elif isinstance(merge_dict_or_list, dict):
            for k, v in merge_dict_or_list.items():
                if k not in self:
                    self.time_accum[k] = v
                    self.counts[k] = 0 if v == 0.0 else 1
        else:
            raise Utils_Exception('TimeTracker.merge_categories - merge requires either a dict or list-like object', merge_dict_or_list_type=type(merge_dict_or_list))
        return self._update_dict_view()


TRY_MAX_RETRY = 15
TRY_MAX_SLEEP = 20


def try_listdir(from_directory, max_io_retry=TRY_MAX_RETRY, max_sleep=TRY_MAX_SLEEP):
    """ try_listdir() provides listdir support with retry in case of unreliable
    LAN connections.
    try_listdir(directory)
    returns a list (possibly empty) if successful, otherwise None
    """
    retry_count = 0
    while True:
        try:
            file_list = os.listdir(from_directory)
            break
        except:
            retry_count += 1
            if retry_count > max_io_retry:
                print('try_listdir_failed=',
                      "try_listdir({}) failed, {} retries exceeded...".format(from_directory, max_io_retry))
                return []
            time.sleep(min(retry_count, max_sleep))
    return file_list




def try_open(file_name, mode_value, max_retry=TRY_MAX_RETRY, max_sleep=TRY_MAX_SLEEP, max_wait_seconds=None, gzip_enabled=True,
             compress_level=9):
    """ try_open() provide retry support over unreliable LAN connections and to get around spurious AV induced permission issues.
    file_handle = open(...)
    """
    start_time = time.time()
    retry_count = 0
    while True:
        try:
            if gzip_enabled:
                f = gzip.open(file_name, mode_value, compresslevel=compress_level)
            else:
                f = open(file_name, mode_value)
            break
        except Exception as exc:
            retry_count += 1
            if max_wait_seconds is not None:
                if time.time() - start_time > max_wait_seconds:
                    raise Utils_Exception("try_open with max_wait_seconds failed", time_now=now(), filename=file_name,
                                          max_retry=max_retry, max_sleep=max_sleep, max_wait_seconds=max_wait_seconds,
                                          gzip_enabled=gzip_enabled, compress_level=compress_level)
                time.sleep(min(0.1 * retry_count, max_sleep))
            else:
                if retry_count > max_retry:
                    raise Utils_Exception("try_open failed", time_now=now(), filename=file_name,
                                          max_retry=max_retry, max_sleep=max_sleep, max_wait_seconds=max_wait_seconds,
                                          gzip_enabled=gzip_enabled, compress_level=compress_level)

                if retry_count > 1:
                    print("{}: try_open({}): failed attempt {}, retry pending after sleep, exception {}".format(now(), file_name, retry_count, sys.exc_info()[0]))
                    raise exc
                time.sleep(min(retry_count, max_sleep))

    return f


def try_replace(from_filename, to_filename, max_retry=TRY_MAX_RETRY, max_sleep=TRY_MAX_SLEEP):
    """ try_replace() provides rename/replace support with retry in case of unreliable
    LAN connections and interference from virus scanning software creating spurious permission errors
    try_replace_(from, to)
    returns True if successful, otherwise False
    """
    retry_count = 0
    completed_flag = False
    success_flag = False

    while completed_flag == False:
        try:
            os.replace(from_filename, to_filename)
            success_flag = True
            completed_flag = True
        except:
            retry_count += 1
            if retry_count > 1:
                print("{}: try_replace({}) with ({}) failed attempt {},  sleeping ...".format(now(), from_filename, to_filename, retry_count))
            if retry_count > max_retry:
                completed_flag = True
            else:
                time.sleep(min(max_sleep,retry_count))
    return success_flag


def try_remove(file_name, max_io_retry=TRY_MAX_RETRY, max_sleep=TRY_MAX_SLEEP):
    """ try_remove() provide remove support with retry in case of unreliable
    LAN connections.
    try_remove(filename)
    returns True if successful, otherwise False
    """
    retry_count = 0
    while True:
        try:
            os.remove(file_name)
            break
        except:
            retry_count += 1
            if retry_count > max_io_retry:
                print("{}: try_remove({}): failed, {} retries exceeded...".format(now(), file_name, max_io_retry))
                return False
            if retry_count > 1:
                print("{}: try_remove ({}): failed attempt {},  sleeping ...".format(now(), file_name, retry_count))
            time.sleep(max(max_sleep, retry_count))

    return True



################
# named object cache
#    The cache saves and loads based on a name/meta parameters that identify the context and
#    detect changes in expected contents.
#    parameters must be consistent across save/load (and get_filename if used) to ensure
#    that hashed contents of the file are consistent with the data.
#    for singleton type objects that only change with version,
#    a friendly name of the object can be passed as the id_data_fields
#    More complex uses must supply id_data_fields that uniquely identify the object
#    and the state information applicable when it was created.
#    The contents of the cached_object, which can be a class, list, etc, are written
#    in pickle format using gzip compression.
#
#    cache_dir specifies absolute or relative cache file location.
#    app_prefix identifies the current application and use case and should be unique in your environment,
#    app_version the version of the app, which changes when cache would be invalidated,
#    key_data_fields are optional fields used in addition to version (and utils version)
#    and app_prefix to compute a hash key for the filename.
#    host_specific is optional and if provided as True indicates that cache entries should
#    include the host name in both name and key value to prevent inadvertent loading in
#    undesired or differently configured environments.

ut_cache_suffix = '.pkgz'

def cache_get_filename(cache_dir, app_prefix, app_version, *key_data_fields,
                       added_filename_info=None,
                       host_specific=False, alt_dir=None, alt_base_filename=None,
                       alt_path_filename=None) :
    """ cache_get_filename() - returns assigned filename used by named object cache
    for an object with configured prefix, version, and key data fields.
    Returns a filename in complete form as used by cache service.
    """

    if alt_path_filename is not None :
        _, base_filename = os.path.split(alt_path_filename)
        return alt_path_filename, base_filename

    if alt_base_filename is not None:
        if alt_dir is None:
            alt_dir = cache_dir
        cache_file_name = os.path.join(alt_dir, alt_base_filename)
        return cache_file_name, alt_base_filename

    if host_specific :
        host_segment = '_' + socket.gethostname().lower() + '_'
    else:
        host_segment = '_'

    extra_info = ('_' + added_filename_info.replace('.','_').replace(':','_').replace('\\','_').replace('/','_')) if added_filename_info is not None else ''

    key_str = key_concat(app_prefix, app_version, host_segment, _utils_general_version, *key_data_fields)

    cache_file_key = hashlib.sha224(key_str.encode('utf-8')).hexdigest()[0:30]
    cache_base_filename = app_prefix  + "_v_" + str(app_version).replace('.','_') + host_segment + cache_file_key + extra_info + ut_cache_suffix

    cache_file_name = os.path.join(cache_dir, cache_base_filename)

    return cache_file_name, cache_base_filename


def cache_load(cache_dir, app_prefix, app_version, *key_data_fields,
               host_specific=False, alt_dir=None,
               alt_base_filename=None, alt_path_filename=None,
               update_message=None, use_cloudpickle=False) :
    """ cache_load() - implements load for named object cache
    Returns a cached object or None if a cached object doesn't exist or couldn't be
    loaded.
    """
    global cloudpickle
    if use_cloudpickle and cloudpickle is None:
        raise Exception("cloudpickle not supported here")
    pickle_module = pickle if not use_cloudpickle else cloudpickle
    cache_file_name, cache_base_filename = cache_get_filename(cache_dir, app_prefix, app_version, *key_data_fields,
                                                              host_specific=host_specific, alt_dir=alt_dir,
                                                              alt_base_filename=alt_base_filename,
                                                              alt_path_filename=alt_path_filename)
    cache_obj = None

    try :
        with gzip.open(cache_file_name, "rb") as f :
            cache_obj = pickle_module.load(f)
    except Exception as ex_info:
        if update_message is not None:
            print('{}: cache_load not found: {} - {} {} - file {} - exc {}'.format(now(), update_message, app_prefix, app_version, cache_file_name, ex_info))
        cache_obj = None

    return (cache_obj, cache_base_filename)


def cache_save(cache_dir, app_prefix, app_version, app_object_to_store, *key_data_fields,
               host_specific=False, alt_dir=None, alt_base_filename=None,
               alt_path_filename=None, compress_level=7, use_cloudpickle=False):
    """ cache_save() - implements save for a named object cache
    app_object_to_store is a python object (class, list, seq, etc) that is saved to the named
    cache file.  The same form is returned on load.
    Returns success / failure and filename - ignores errors writing the requested cache file, if any.
    """
    global cloudpickle
    if use_cloudpickle and cloudpickle is None:
        raise Exception('cloudpickle not supported')
    pickle_module = pickle if not use_cloudpickle else cloudpickle

    cache_file_name, cache_base_filename = cache_get_filename(cache_dir, app_prefix, app_version, *key_data_fields,
                                                              host_specific=host_specific, alt_dir=alt_dir,
                                                              alt_base_filename=alt_base_filename, alt_path_filename=alt_path_filename)

    success_flag = False
    try :
        with gzip.open(cache_file_name, "wb", compresslevel=compress_level) as f :
            pickle_module.dump(app_object_to_store, f, protocol=4)
        success_flag = True
    except :
        raise Utils_Exception('cache_save: unable to pickle or save file',cache_file_name=cache_file_name)
        pass

    return (success_flag, cache_base_filename)

def cache_wrap(cache_dir, app_prefix, app_version, function_to_call, function_arg_list, *key_data_fields,
               host_specific=False, alt_dir=None, alt_base_filename=None,
               alt_path_filename=None, update_message=None, compress_level=9, use_cloudpickle=False) :
    """ cache_wrap() - wraps a function call and its return object as a cache managed request.
    The cache key contents are assumed changed when any of the key_data_fields contents are changed.
    The return value is the same as the underlying function.  If the app needs to know the filename,
    use the cache_get_filename() call with the corresponding values.
    """
    result_obj, cache_file = cache_load(cache_dir, app_prefix, app_version, *key_data_fields, host_specific=host_specific,
                                        alt_dir=alt_dir, alt_base_filename=alt_base_filename,
                                        alt_path_filename=alt_path_filename, 
                                        use_cloudpickle=use_cloudpickle
                                        )
    if result_obj is None:
        if update_message is not None:
            print('{}: cache_wrap start: {} - {} {} {}'.format(now(), update_message, app_prefix, app_version, cache_file))
        result_obj = function_to_call(*function_arg_list)
        if update_message is not None:
            print('{}: cache_wrap complete: {}'.format(now(), update_message))
        result, cache_file = cache_save(cache_dir, app_prefix, app_version, result_obj, *key_data_fields,
                                        host_specific=host_specific, compress_level=compress_level, 
                                        use_cloudpickle=use_cloudpickle)
    return result_obj

def get_random_unique_string(key_length=40):
    return ''.join([random.choice(string.ascii_lowercase + string.digits) for n in range(key_length)])

load_file_to_dataframe_neg9s = -999999
last_zip_container_name = None
last_zip_container_is_tarfile = None
last_zip_container_handle = None
last_zip_container_mode = None

def load_file_to_dataframe_close_container():
    global last_zip_container_name, last_zip_container_is_tarfile, last_zip_container_handle, last_zip_container_mode
    if last_zip_container_name is not None:
        if last_zip_container_is_tarfile:
            last_zip_container_handle.close()
        else:
            last_zip_container_handle.close()
        last_zip_container_name = None
        last_zip_container_is_tarfile = None
        last_zip_container_handle = None
        last_zip_container_mode = None
    return

def load_file_to_dataframe(file_name, zip_container=None, keep_container_open=False,
                           fix_dict=None, missing_as_nan_neg9s=False,
                           sheet_name=0, skiprows=0,
                           auto_fixup=True, date_column_format=None,
                           eval_fixup_rows=2011, rename_columns=None, default_columns=None, keep_columns=None, drop_columns=None,
                           cache_dir=None, host_specific=True, _input_f=None, path_prefix=None):
    """ load_file_to_dataframe() loads a pandas dataframe with added logic to automatically fix NaNs and convert to a
    consistent type for each column.
    The input filename can be .csv, .xlsx, or other excel related filename.
    if specified, cache_dir enables cache and specifies its location - based on filename size/date information for cache key
        version of the loaded/pre-processed pandas dataframe.
    fix_dict is an optional dictionary of column name to default value mapping; note that automatic conversion to string or float is also done
        when a column is specified and the default is either string or float in the calling params.
        If fix_dict contains a '*' entry, its type is used for any columns not explicitly mapped in fix_dict
    sheet_name must refer to a single sheet, as the logic does not support the dict of dataframes return mode.
    auto_fixup - specifies whether automatic fixup and homogenization should be performance (float-like to 0.0, string-like to '')
    drop_columns - a list of zero or more columns to be dropped from the input file if they exist, or None if not applicable
    keep_columns - a list of one or more columns to be retained from the input file, excluding all others, or None to use input files
    cache_dir - specifies cache location - pre-processed files are cached - if not specfied or None, caching is not provided.
    host_specific - specifies whether cache entries are specific to current host name (default) or generic (False) for appropriate shared environments
    returns the dataframe or raises an error if an error occurs.
    """
    global last_zip_container_name, last_zip_container_is_tarfile, last_zip_container_handle, last_zip_container_mode
    close_container = None

    file_name_base_info = os.path.basename(file_name).replace('.', '_')
    if path_prefix:
        if zip_container:
            zip_container = os.path.join(path_prefix, zip_container)
        else:
            file_name = os.path.join(path_prefix, file_name)

    if cache_dir is not None and _input_f is None:
        physical_file = file_name if zip_container is None else zip_container
        file_m_timestamp = os.path.getmtime(physical_file)
        statinfo = os.stat(physical_file)
        file_size = statinfo.st_size
        return cache_wrap(cache_dir, f'load_file_to_dataframe_{file_name_base_info}', _utils_general_version,
                          load_file_to_dataframe, (file_name, zip_container, keep_container_open, fix_dict, missing_as_nan_neg9s,
                                                   sheet_name, skiprows, auto_fixup, date_column_format,
                                                   eval_fixup_rows, rename_columns, default_columns, keep_columns, drop_columns),
                          ('' if zip_container is None else '{}:'.format(zip_container)) + file_name, file_m_timestamp, file_size, missing_as_nan_neg9s, sheet_name, skiprows, fix_dict, auto_fixup, date_column_format,
                                    rename_columns, default_columns, keep_columns, drop_columns, host_specific=host_specific)


    # note that recursive calls have no cache_dir, so they fall through...

    if file_name[-4:].lower() in ('.csv', '.txt'):
        excel_mode = False
    else:
        excel_mode = True

    if zip_container is not None:
        if last_zip_container_mode == excel_mode and last_zip_container_name == zip_container:
            if last_zip_container_is_tarfile:
                tfh = last_zip_container_handle
                file_access_name_handle = tfh.extractfile(file_name)
            else:
                zip_object = last_zip_container_handle
                if excel_mode is False:
                    file_access_name_handle = zip_object.open(file_name, "r")
                else:
                    file_access_name_handle = zip_object.open(file_name, "rb")
        else:
            if tarfile.is_tarfile(zip_container):
                if excel_mode is False:
                    tfh = tarfile.open(name=zip_container, mode='r')
                else:
                    tfh = tarfile.open(name=zip_container, mode='rb')
                file_access_name_handle = tfh.extractfile(file_name)
                last_zip_container_is_tarfile = True
                last_zip_container_handle = tfh
            else:
                zip_object = zipfile.ZipFile(zip_container if _input_f is None else _input_f, "r")
                if excel_mode is False:
                    file_access_name_handle = zip_object.open(file_name, "r")
                else:
                    file_access_name_handle = zip_object.open(file_name, "rb")
                last_zip_container_is_tarfile = False
                last_zip_container_handle = zip_object
            # we'll close on return if not keeping open
            last_zip_container_name = zip_container
            last_zip_container_mode = excel_mode
    else:
        file_access_name_handle = file_name if _input_f is None else _input_f

    # first, adapt if .csv rather than a presumed excel file
    if excel_mode is False:
        temp_df = pd.read_csv(file_access_name_handle, low_memory=False)
        sheet_dict = dict(default=temp_df)
    else:
        # show_vars(file_access_name_handle=file_access_name_handle, sheet_name=sheet_name, skiprows=skiprows)
        temp_df = pd.read_excel(file_access_name_handle, sheet_name=sheet_name, skiprows=skiprows, engine='openpyxl')
        if not isinstance(temp_df, dict):
            sheet_dict = dict(default=temp_df)
        else:
            sheet_dict = temp_df

    if not isinstance(file_access_name_handle, str):
        file_access_name_handle.close()

    for sheet_tag, temp_df in sheet_dict.items():
        
        if drop_columns is not None:
            for drop_one_column in drop_columns:
                if drop_one_column in temp_df.columns:
                    temp_df.drop(columns=[drop_one_column], inplace=True)

        if rename_columns is not None:
            for rename_orig_col, rename_new_col in rename_columns.items():
                if rename_orig_col in temp_df.columns and rename_new_col not in temp_df.columns:
                    temp_df.rename(columns={rename_orig_col: rename_new_col}, inplace=True)

        if default_columns is not None:
            for create_column_name, create_default_value in default_columns.items():
                if create_column_name not in temp_df.columns:
                    temp_df[create_column_name] = [create_default_value for x in range(len(temp_df))]

        if keep_columns is not None:
            temp_df = sheet_dict[sheet_tag] = temp_df[keep_columns].copy()

        # there is an option, yes needed, to convert datetime objects as column names to text.. process first
        column_list = list(temp_df.columns)

        # not sure whether this date_column_format would work.... as of 12/2019
        if date_column_format is not None:
            rename_date_columns = {}
            for test_date_column in column_list:
                if isinstance(test_date_column, datetime.datetime):
                    new_column_name = test_date_column.strftime(date_column_format)
                    rename_date_columns[test_date_column] = new_column_name
            if len(rename_date_columns):
                temp_df.rename(columns=rename_date_columns, inplace=True)
            column_list = temp_df.columns

        # next is logic to autofill NA values and to adaptively convert all data to homogenous types...

        str_convert_columns = []
        float_convert_columns = []
        int_convert_columns = []

        if fix_dict is not None and '*' in fix_dict:
            fix_default = True
            fix_default_type = fix_dict['*']
        else:
            fix_default = False
            fix_default_type = None

        fix_column_info = {}
        if fix_dict is not None:
            for data_col in column_list:
                if data_col in fix_dict:
                    set_to_type = fix_dict[data_col]
                elif fix_default:
                    set_to_type = fix_default_type
                else:
                    set_to_type = None

                if set_to_type is not None:
                    fix_column_info[data_col] = set_to_type
                    if isinstance(set_to_type, float):
                        float_convert_columns.append(data_col)
                    elif isinstance(set_to_type, str):
                        str_convert_columns.append(data_col)
                    elif isinstance(set_to_type, int):
                        int_convert_columns.append(data_col)

        if auto_fixup and fix_default is False:
            if len(temp_df) < eval_fixup_rows:
                temp_df_sample = temp_df
            else:
                temp_df_sample = temp_df.sample(n=eval_fixup_rows)

            for fix_column in column_list:
                if fix_column not in fix_column_info:
                    float_count = 0
                    int_count = 0
                    str_count = 0
                    other_count = 0

                    for test_val in temp_df_sample[fix_column]:
                        if not pd.isnull(test_val):
                            if isinstance(test_val, int):
                                int_count += 1
                            elif isinstance(test_val, float):
                                float_count += 1
                            elif isinstance(test_val, str):
                                str_count += 1
                            else:
                                other_count += 1

                    max_count = max(float_count, int_count, str_count, other_count)

                    if str_count > 0:
                        fix_column_info[fix_column] = ''
                        str_convert_columns.append(fix_column)
                    elif float_count > 0:
                        # integers don't count here, any float overrides integer determination.
                        if missing_as_nan_neg9s:
                            fix_column_info[fix_column] = np.nan
                        else:
                            fix_column_info[fix_column] = 0.0
                        float_convert_columns.append(fix_column)
                    elif int_count > 0:
                        if missing_as_nan_neg9s:
                            fix_column_info[fix_column] = load_file_to_dataframe_neg9s
                        else:
                            fix_column_info[fix_column] = 0
                        int_convert_columns.append(fix_column)
                    else:
                        fix_column_info[fix_column] = ''

            del temp_df_sample

        temp_df.fillna(value=fix_column_info, inplace=True)
        for fix_column in str_convert_columns:
            try:
                temp_df[fix_column] = temp_df[fix_column].map(lambda field_val: str(field_val))
            except Exception as ex_info:
                raise Utils_Exception('load_file_to_dataframe: fixup str failed', exception=str(ex_info), fix_column=str(fix_column), temp_df_fix_column_type=type(temp_df[fix_column]))
        for fix_column in float_convert_columns:
            try:
                temp_df[fix_column] = temp_df[fix_column].map(lambda field_val: float(field_val))
            except Exception as ex_info:
                raise Utils_Exception('load_file_to_dataframe: fixup float failed', exception=str(ex_info), fix_column=str(fix_column), temp_df_fix_column_type=type(temp_df[fix_column]))
        for fix_column in int_convert_columns:
            try:
                temp_df[fix_column] = temp_df[fix_column].map(lambda field_val: int(field_val))
            except Exception as ex_info:
                raise Utils_Exception('load_file_to_dataframe: fixup int failed', exception=str(ex_info), fix_column=str(fix_column), temp_df_fix_column_type=type(temp_df[fix_column]))

    if keep_container_open is False and zip_container:
        load_file_to_dataframe_close_container()            

    if len(sheet_dict) == 1:
        return_value = list(sheet_dict.values())[0]
    else:
        return_value = sheet_dict
    return return_value


def save_dataframe_to_file(dataframe_or_records, file_name, *, path_prefix=None, sheet_name='Sheet1', sheet_names=None,
                           keep_columns=None, drop_columns=None, sort_columns=False,
                           index=False, freeze_panes=(1, 0), print_status=True, print_status_extra=None, _output_f=None):
    """
    save_dataframe_to_file - saves file as a csv or xlsx based on file extension
    """
    if sheet_names is None:
        sheet_names = [sheet_name]
        dataframes_or_records = [dataframe_or_records]
    else:
        dataframes_or_records = dataframe_or_records

    if path_prefix is not None:
        target_file = os.path.join(path_prefix, file_name)
    else:
        target_file = file_name

    if target_file.endswith('.xlsx'):
        writer = pd.ExcelWriter(target_file if _output_f is None else _output_f, engine='xlsxwriter',
                                engine_kwargs={'options': {'strings_to_urls': False, 'use_zip64': True}})
    elif target_file.endswith('.xls') or target_file.endswith('.oda'):
        # TODO: this may need a different engine
        writer = pd.ExcelWriter(target_file if _output_f is None else _output_f, engine='xlsxwriter')
    elif target_file.endswith('csv') is False:
        raise Utils_Exception('save_dataframe_to_file: output must be .csv or .xlsx', target_file=target_file)

    if print_status:
        print('{}: {}{} to'.format(now(), 'Writing' if _output_f is None else 'Writing(stream)', '' if print_status_extra is None else ' ' + print_status_extra), target_file)

    for output_index, (dataframe_or_records, sheet_name) in enumerate(zip(dataframes_or_records, sheet_names)):
        if False:
            if isinstance(dataframe_or_records, list) and isinstance(dataframe_or_records[0], dict):
                df = pd.DataFrame(dataframe_or_records)
            else:
                df = dataframe_or_records
        df = pd.DataFrame(dataframe_or_records)

        if keep_columns is None or len(keep_columns) == 0:
            check_for_columns = list(df.columns)
        else:
            check_for_columns = keep_columns

        if drop_columns is not None:
            check_for_columns = [col for col in check_for_columns if col not in drop_columns]

        keep_columns_adj = []
        for cur_column in df.columns:
            if cur_column in check_for_columns:
                keep_columns_adj.append(cur_column)

        if sort_columns:
            keep_columns_adj.sort(key=lambda x: x.lower())

        if target_file.endswith('.xlsx'):
            df.to_excel(writer, sheet_name=sheet_name, index=index, columns=keep_columns_adj, freeze_panes=freeze_panes)
        else:   # write a .csv
            if output_index != 0 or len(sheet_names) > 1:
                target_file = target_file[:-4] + '_' + sheet_name + '.csv'
            df.to_csv(target_file if _output_f is None else _output_f, index=index, columns=keep_columns_adj)

    if target_file.endswith('.xlsx'):
        # writer.use_zip64()
        writer.close()

    return target_file



def elapsed_time_in_seconds(prior_datetime, comparison_time=None) :
    """ returns time elapsed in seconds since a prior datetime value and a new datatime value.
    if comparison_time is provided, it must be later than prior_ and is used for
    the elapsed calculation.  The current time is always the returned timestamp.
    """
    new_time = datetime.datetime.now()
    if comparison_time is None:
        comparison_time = new_time
    delta_time = comparison_time - prior_datetime
    elapsed = delta_time.seconds + delta_time.days * 3600 * 24
    return elapsed, new_time


def remove_duplicates_in_list(in_list):
    """ removes duplicate values in a list and returns the de-duped list """
    clean_list = {}
    for entry in in_list:
        if entry not in clean_list:
            clean_list[entry] = True
    return list(clean_list)


def trim_dictionary(dict_container, remove_keys):
    if not isinstance(remove_keys, list):
        remove_keys = [remove_keys]
    for remove_key in remove_keys:
        if remove_key in dict_container:
            del dict_container[remove_key]
    return


# consider numba - move to clt_tools maybe
def win_loss_value(s1, s2, score_is_loss=True):
    """
    compare two scores and return positive value if s1 is better, 0 if the same, negative if s2 is better, based on score_is_loss or
    alternatively it is a gain.
    This has the property that 100 implies a 2:1 winner:loser ratio, and follows in log2 fashion, with 200 at 4:1, and so, on.
    :param s1:
    :param s2:
    :param score_is_loss:
    :return:
    """
    if s1 == s2:
        return 0.0
    elif (score_is_loss and s1 < s2) or (score_is_loss is False and s1 > s2):
        res_mult = 100.0
    else:
        res_mult = -100.0
    min_val = min(s1, s2)
    max_val = max(s1, s2)
    if min_val < 0 and max_val > 0:
        adj_value = mean((abs(s1), abs(s2))) - min_val
        s1 += adj_value
        s2 += adj_value
    if 0.0 in (float(s1), float(s2)):
        return 10000.0 * res_mult
    if s1 < 0:
        s1 *= -1.0
        s2 *= -1.0
    return res_mult * math.log(max(s1, s2) / min(s1, s2), 2)


def get_g_test_p_value(obs_1, hit_1, obs_2, hit_2):
    if obs_1 <= 0 or obs_2 <= 0:
        return 1.0
    # G test with scipy:
    obs_info = np.array([[obs_1, hit_1], [obs_2, hit_2]])
    g, p, dof, expctd = chi2_contingency(obs_info, lambda_="log-likelihood")
    # show_vars_semi_pass(obs_1=obs_1, hit_1=hit_1, obs_2=obs_2, hit_2=hit_2, g=g, p=p, dof=dof, expctd=expctd)

    return p


# this is an invertible shuffle, so that the original order can be recovered by using the returned order_list
def shuffle_list_invertible(input_list, *, order_list=None):
    data_length = len(input_list)
    if order_list is None:
        order_list = np.arange(data_length)
        np.random.shuffle(order_list)
    shuffled_data = [input_list[k] for k in order_list]
    new_order_list = np.zeros_like(order_list)
    new_order_list[order_list] = np.arange(data_length)
    return shuffled_data, new_order_list
 
