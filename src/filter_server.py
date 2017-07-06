import logging
import requests
import json
import datetime
import argparse
import ipaddress
import sqlite3

from flask import Flask
from flask import request
from flask import g

from util import *


## This function handles the core logic of the server. If a rule
## exists for a connection and enough time has elapsed, the data is
## forwarded to the destination address.
def can_send(in_address):
    'True if the a message from the given address can be forwarded.'
    rule_table = get_rule_table()
    rule = rule_table.get(in_address)
    delay_table = get_delay_table()
    time_of_last_forward = delay_table.get(rule._in, datetime.datetime.now() - rule.delay)
    logging.info('%s >= %s', time_since(time_of_last_forward), rule.delay)
    if time_since(time_of_last_forward) >= rule.delay:
        delay_table.update(rule._in, datetime.datetime.now())
        return True
    else:
        return False
    




## The route rule is a description of how data from an incoming
## address will be handled. This object maps directly to the
## representation of a rule in a rule file. The in address is the ip
## address of the incoming data, the out address is the destination ip
## address, and the out_port is the destination port. There is no
## input port inside a route rule because all rules have the same
## input port, the port the server is running on. The delay value is
## the minimum amount of time between input requests allowed. If data
## is sent from the same ip address before the delay has elapsed, the
## data will be dropped.
class RouteRule(object):
    'A rule for forwarding data.'
    def __init__(self, _in, out, out_port, delay = datetime.timedelta(seconds = 0)):
        self._in = _in
        self.out = out
        self.out_port = out_port
        self.delay = delay

## There are many exceptions here to account for all the possible
## errors when parsing a rule file. Rule files are a subset of JSON,
## and so a simple JSON parser cannot account for all possible
## errors. The exceptions below cover what happens if the structure of
## the json file is bad (i.g. the outermost object is a list), there's
## a missing required field, there's a field that doesn't exist, and
## if there's an invalid value in a field. There are many ways to
## fail, so having different exceptions for each kind of failure helps
## debug rule files.
class BadRuleFileException(Exception):
    'There was a generic parsing error on a rule file.'
    def __init__(self, file_path):
        self.file_path = file_path
    def __repr__(self):
        return 'Parsing error in file %s.' % (self.file_path,)

class BadRuleException(Exception):
    def __init__(self):
        self.index = index
        self.value = value
    def __repr__(self):
        return 'Parsing error in file %s at line %d. Missing required key value %s.' % (self.file_path, self.index, self.value,)

class UnknownRuleValueException(Exception):
    'A routing rule contains an unexpected binding.'
    def __init__(self, file_path, index, value):
        self.file_path = file_path
        self.index = index
        self.value = value
    def __repr__(self):
        return 'Parsing error in file %s at line %d. Unknown key value %s.' % (self.file_path, self.index, self.value,)

class RuleFieldTypeException(Exception):
    'The field in the given rules file is the wrong type.'
    def __init__(self, file_path, index, key, value, predicate):
        self.file_path = file_path
        self.index = index
        self.key = key
        self.value = value
        self.predicate = predicate
    def __repr__(self):
        return 'Parsing error in file %s at line %d. Bad value for key %s. Predicate %s returned false on value %s.' % (self.file_path, self.index, self.key, self.predicate, self.value,)

class RuleTable(object):
    def __init__(self, init_rules = []):
        'Set up an empty rule table, add any rules given in the init function, and set up a null default rule.'
        self.rules = {}
        for rule in init_rules:
            self.rules[rule._in.exploded] = rule
        if not 'DEFAULT' in self.rules:
            self.rules['DEFAULT'] = RouteRule('DEFAULT', 'NULL', 0)
    def set(self, new_rule):
        'Add a new routing rule to the table.'
        self.rules[new_rule._in.exploded] = new_rule
    def get(self, key):
        'Get the routing rule for the given input IP address.'
        try:
            return self.rules[key.exploded]
        except KeyError:
            return self.rules['DEFAULT']

class MissingRuleValueException(Exception):
    'A routing rule is missing a required binding.'
    def __init__(self, file_path, index, value):
        self.file_path = file_path

## These are just some global constants that determine which fields
## can and must be in a rule file.
VALID_KEYS = {'in', 'out', 'delay', 'out_port'}
REQUIRED_KEYS = {'out', 'out_port'}

## These two tests are used for checking that the fields in a rule
## file are valid and are placed in the exceptions for parsing errors
## so that whoever catches the error has access to the test.
def is_positive_or_zero_integer(n):
    'True if argument is an integer greater than or equal to zero.'
    return (n == int(n)) and n >= 0

def is_positive_integer(n):
    'True if the argument is an intger greater than zero.'
    return (n == int(n)) and n >= 0

## Most of the code in this module is in or supporting this
## load_rule_file function. The function opens a file at the given
## path, parses it, checks for type errors, and returns a list of rule
## objects.
def load_rule_file(file_path):
    'Load the routing rules in FILE_PATH.'
    try:
        with file(file_path) as f_obj:
            rules = json.load(f_obj)
    except ValueError:
        raise BadRuleFileException(file_path)
    if type(rules) is not list:
        BadRuleFileException(file_path)
    for index, rule in enumerate(rules):
        ## Check that the top level JSON data structure is a list and not a hash.
        if type(rule) is not dict:
            raise BadRuleException(file_path, index)
        ## Check that all keys are valid. Ideally there would be a way to toggle
        ## this from a crash to a warning, but, as far as I know, there's no way
        ## to resume from where an exception is raised after its been handled.
        ## I might just have to add a logging call down here.
        for key in rule.keys():
            if key not in VALID_KEYS:
                raise UnknownRuleValueException(file_path, index, key)
        ## Test that the optional input IP address is valid if it exists.
        ## If it does not exist, set it to a sane default.
        try:
            assert is_valid_ipv6_address(rule['in'])
        except KeyError:
            rule['in'] = 'DEFAULT'
        except AssertionError:
            raise RuleFieldTypeException(file_path,
                                         index,
                                         'in',
                                         rule['in'],
                                         is_valid_ipv6_address)
        ## Test that the mandatory output IP address exists and is valid.
        try:
            assert is_valid_ipv6_address(rule['out'])
        except KeyError:
            MissingRuleValueException(file_path, index, key)
        except AssertionError:
            raise RuleFieldTypeException(file_path,
                                         index,
                                         'out',
                                         rule['out'],
                                         is_valid_ipv6_address)
        ## Test that the destination port exist and is valid.
        try:
            assert is_positive_integer(int(rule['out_port']))
        except KeyError:
            raise MissingRuleValueException(file_path,
                                      index,
                                      'out_port')
        except (AssertionError, ValueError):
            raise RuleFieldTypeException(file_path,
                                          index,
                                          'out_port',
                                          rule['out_port'],
                                          is_positive_integer)
        ## Test the the optional delay address is valid if it exists.
        ## If it does not exist, set it to a sane default.
        try:
            assert is_positive_or_zero_integer(int(rule['delay']))
        except KeyError:
            rule['delay'] = 0
        except (AssertionError, ValueError):
            raise RuleFieldTypeException(file_path,
                                         index,
                                         'delay',
                                         rule['delay'],
                                         is_positive_or_zero_integer)
    return RuleTable(RouteRule(_in = ipaddress.ip_address(rule['in']) if rule['in'] != 'DEFAULT' else 'DEFAULT',
                               out = ipaddress.ip_address(rule['out']),
                               out_port = rule['out_port'],
                               delay = datetime.timedelta(seconds = int(rule['delay'])))
                     for rule in rules)

def time_since(epoch):
    'Return the time elapsed since the given date time argument.'
    return datetime.datetime.now() - epoch

class NoRuleFileException(Exception):
    def __init__(self, path):
        self.path = path
    def __repr__(self):
        return 'Could not find rule file %s' % (self.path,)

RULE_TABLE = None
def get_rule_table():
    'Load the current rule file.'    
    return RULE_TABLE


def make_delay(cursor, row):
    ip_address_str, duration_str = row
    return Delay(ipaddress.IPv6Address(ip_address_str),
                 datetime.datetime.strptime(duration_str, '%Y-%m-%dT%H:%M:%S'))


## Initialize delay table with Schema.
DELAY_TABLE = sqlite3.connect(':memory:')
with file('delay_schema.sql') as f_obj:
    DELAY_TABLE.cursor().execute(f_obj.read())
DELAY_TABLE.row_factory = make_delay # Changes the way queries are represented.    

class Delay(object):
    def __init__(self, ip_address, duration):
        self.ip_address = ip_address
        self.duration = duration
    def get_ip(self):
        return self.ip_address
    def get_duration(self):
        return self.duration

class DelayTable(object):
    'A connection to a delay table database.'
    def __init__(self, db):
        self.db = db
    def get(self, ip_addr, default):
        'Get the delay on the given IP address. The \'ip_addr\' argument is an IPv6Address object. Returns default if no value with given IP address could be found.'
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM delay WHERE origin_machine=?',
                       (ip_addr.exploded,))
        result = cursor.fetchone()
        if result:
            return result.get_duration()
        else:
            logging.info('Could not find %s in delay table. Returning default value instead.', ip_addr)
            return default
    
    def update(self, ip_addr, time):
        'Update the delay on the given IP address. Creates a new row if address doesn\'t already have a delay. The \'ip_addr\' argument is an IPv6Address object and the \'time\' argument is a datetime object.'
        cursor = self.db.cursor()
        exists = self.get(ip_addr, None) ## Note, ip_addr does not need to be exploded here, because it's calling a public method.
        if not exists:
            cursor.execute('INSERT INTO delay (origin_machine, time_elapsed) VALUES (?, ?)',
                           (ip_addr.exploded,
                            time.replace(microsecond = 0).isoformat(),))
        else:
            cursor.execute('UPDATE delay SET time_elapsed=? WHERE origin_machine=?',
                           (time.replace(microsecond = 0).isoformat(),
                            ip_addr.exploded,))


def get_delay_table():
    return DelayTable(DELAY_TABLE)

app = Flask(__name__) # Create the web application.

@app.errorhandler(500)
def internal_logging(exception):
    try:
        raise exception
    except BadRuleFileException, e:
        logging.error(repr(e))
        logging.debug('Is the bad rule file not valid JSON? Is the top level object not a list?')
    except BadRuleException, e:
        logging.error(repr(e))
        logging.debug('Is the bad rule not a dictionary?')
    except UnknownRuleValueException, e:
        logging.error(repr(e))
        logging.debug('Is the unknown key value not one of the following %s?', VALID_KEYS)
    except MissingRuleValueException, e:
        logging.error(repr(e))
        logging.debug('Is there not a key value for all of the following %s?', REQUIRED_KEYS)
    except RuleFieldTypeException, e:
        logging.error(repr(e))
        if e.predicate == is_valid_ipv6_address:
            logging.debug('Is the bad value not a valid ipv6 address? A plain ipv4 address will not work.')
        elif e.predicate == is_valid_ipv6_address == is_positive_or_zero_integer:
            logging.debug('Is the bad value not a positive integer or zero?')
        else:
            logging.debug('Is the value not valid in some way?')
    except NoRuleFileException, e:
        logging.error(repr(e))
        logging.debug('Is there no rule file in the experiment directory?')
    except CouldNotForwardException, e:
        logging.error(repr(e))
        logging.debug('Is there a server listening at [%s]?' % (e.destination,))
    except Exception, e:
        logging.critical(repr(e))
        logging.debug('Nothing is known about the last error.')
    return '500'


class CouldNotForwardException(Exception):
    def __init__(self, destination):
        self.destination = destination
    def __repr__(self):
        return 'Could not connect to %s' % (self.destination,)
    
@app.route('/', methods = ('POST', 'PUT'))
def filter():
    remote_addr = ipaddress.ip_address(unicode(request.remote_addr))
    if not can_send(remote_addr):
        logging.info('Rejected message from %s due to delay limit.', remote_addr)
        return 'Failure'
    rule_table = get_rule_table()
    rule = rule_table.get(remote_addr)
    if rule.out == 'NULL':
        logging.info('Source %s had NULL destination, message not routed.', remote_addr)
        return 'Failure'
    url = 'http://[%s]:%s/' % (rule.out.exploded, rule.out_port)
    try:
        requests.post(url, data = request.data)
    except requests.ConnectionError:
        raise CouldNotForwardException(url)
    logging.info('Forwarded message from %s to %s',
                 remote_addr, rule.out)
    return 'Success'

if __name__ == '__main__':
    logging.basicConfig(level = logging.DEBUG)
    parser = argparse.ArgumentParser(description = 'HTTP filter that forwards HTTP requests but gives them a fixed delay')
    parser.add_argument('--rule-path', help = 'The path to the rule file for this program.', type = str, default = retrieve_file('.RULE'))
    parser.add_argument('--port', help = 'The port to run the server on.', type = is_port_number, default = 5000)
    args = parser.parse_args()
    RULE_PATH = args.rule_path
    PORT = args.port
    print args.port
    RULE_TABLE = load_rule_file(RULE_PATH)
    app.run(host = '::', port = PORT)
    'There was a parsing error found inside of a routing rule.'
    def __init__(self, file_path, index):
        self.file_path = file_path
        self.index = index
    def __repr__(self):
        return 'Parsing error in file %s at line %d.' % (self.file_path, self.index)


