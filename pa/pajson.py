#!/usr/bin/env python3
import collections
import decimal
import json
import re

Token = collections.namedtuple('Token', ['type', 'value', 'line', 'column', 'length', 'cvalue'])
################## KNOWN ISSUES
# Multiline comments with newline characters messes with the error preview

# globals - Oh dear!
_warnings = []
_file_source = ''
_colored_file_lines = []
_file_lines = []

################################################################################
############################ error message near message ########################
################################################################################
## this part is probably the most complex and buggy
def _error_near(tokens, index, type, message):
    global _file_lines
    if type == 'warning':
        type = bcolors.YELLOW + type + bcolors.ENDC
    elif type == 'error':
        type = bcolors.RED + type + bcolors.ENDC
    else:
        type = bcolors.GRAY + type + bcolors.ENDC

    tok = tokens[index]

    #line formatter <line number>|<source>
    line_format = ' {:>' + str(len(str(tok.line + 3))) + '}|{}\n'

    preview = ''
    for i in range(tok.line - 3, tok.line + 2):
        if i > len(_file_lines): break
        if i < 0: continue

        if i != 0:
            preview += line_format.format(str(i), _colored_file_lines[i - 1])

        if i == tok.line:
            preview += line_format.format('', re.sub(r'\S', ' ', _file_lines[tok.line - 1][0:tok.column-1]) + bcolors.WHITE + '^' + bcolors.ENDC + bcolors.LIGHT_GRAY +(tok.length - 1) * '~' + ' ' + message + bcolors.ENDC)


    # line one: error source (<file>:<line>:<column> <message>)
    source_line = bcolors.WHITE + str(_file_source) + ':' + str(tok.line) + ':' + str(tok.column) + ' ' + type + ': ' + bcolors.WHITE + message + bcolors.ENDC

    return source_line + '\n' +  preview

################################################################################
###################################################### token iteration #########
################################################################################
def _token_next(tokens, index):
    index += 1

    # skip all the ignored tokens (newlines, whitespace and comments)
    while tokens[index].type in ['SLCOMMENT', 'MLCOMMENT', 'NEWLINE', 'WHITESPACE']:
        index += 1
    return tokens[index], index

def _token_consume_or_fail(tokens, index, expected):
    tok, index = _token_next(tokens, index)

    received = tok.type

    if isinstance(expected, (list,tuple)):
        if len(expected) > 1:
            expected_str = '\', \''.join(expected[:-1]) + '\' or \'' + expected[-1]
        else:
            expected_str = expected[0]
    else:
        expected_str = expected

    if received not in expected:
        raise TypeError(_error_near(tokens, index, 'error' , 'expected \'' + expected_str + '\' but got \'' + received + '\' instead'))

    return tok, index

def _token_check(tokens, index, expected):
    tok, index = _token_next(tokens, index)
    return tok.type == expected

################################################################################
############### parser values ##################################################
################################################################################
def _parse_value(tokens, index=-1):
    if _token_check(tokens, index, '{'):         return _parse_object(tokens, index)
    if _token_check(tokens, index, '['):         return _parse_array(tokens, index)
    if _token_check(tokens, index, 'STRING'):    return _parse_string(tokens, index)
    if _token_check(tokens, index, 'NUMBER'):    return _parse_number(tokens, index)
    if _token_check(tokens, index, 'BOOL'):      return _parse_bool(tokens, index)
    if _token_check(tokens, index, 'NULL'):      return _parse_null(tokens, index)
    if _token_check(tokens, index, 'EOF'):
        _, index = _token_next(tokens, index)
        raise TypeError(_error_near(tokens, index, 'error', 'could not parse json value, unexpected end of file'))

    _, index = _token_next(tokens, index)
    raise TypeError(_error_near(tokens, index, 'error', 'could not parse json value, unexpected symbol'))

#################### matches an object { ... } ##########################
def _parse_object(tokens, index):
    tok, index = _token_consume_or_fail(tokens, index, '{')

    obj = collections.OrderedDict()

    while not _token_check(tokens, index, '}'):
        key, index = _parse_string(tokens, index)
        _, index = _token_consume_or_fail(tokens, index, ':')
        value, index = _parse_value(tokens, index)

        obj[key] = value
        if not _token_check(tokens, index, '}'):
            _, index = _token_consume_or_fail(tokens, index, [',', '}'])
            if _token_check(tokens, index, '}'):
                _warnings.append(_error_near(tokens, index, 'warning', 'extra comma at end of object key-value pairs'))

    tok, index = _token_consume_or_fail(tokens, index, '}')

    return obj, index

#################### matches an array [ ... ] ##########################
def _parse_array(tokens, index):
    tok, index = _token_consume_or_fail(tokens, index, '[')

    obj = []

    while not _token_check(tokens, index, ']'):
        value, index = _parse_value(tokens, index)

        obj.append(value)

        if not _token_check(tokens, index, ']'):
            _, index = _token_consume_or_fail(tokens, index, [',', ']'])
            if _token_check(tokens, index, ']'):
                _warnings.append(_error_near(tokens, index, 'warning', 'extra comma at end of array'))

    # import pdb; pdb.set_trace()

    tok, index = _token_consume_or_fail(tokens, index, ']')
    return obj, index

#################### matches a string ##########################
def _parse_string(tokens, index):
    tok, index = _token_consume_or_fail(tokens, index, 'STRING')
    return bytes(tok.value[1:-1], "utf-8").decode('unicode_escape'), index

#################### matches a number ##########################
def _parse_number(tokens, index):
    real_json_number = re.compile(r"^-?(([1-9][0-9]*)|0)(\.[0-9]+)?((e|E)[-+]?[0-9]+)?$")

    tok, index = _token_consume_or_fail(tokens, index, 'NUMBER')

    if not real_json_number.match(tok.value):
        _warnings.append(_error_near(tokens, index,'warning', 'ill-formed number'))

    try:
        value = int(tok.value)
    except ValueError as e:
        try:
            value = float(tok.value)
        except ValueError as e:
            try:
                value = decimal.Decimal(tok.value)
            except ValueError as e:
                raise ValueError(_error_near(tokens, index, 'error', 'could not convert string to float'))

    return value, index

#################### matches true|false ##########################
def _parse_bool(tokens, index):
    tok, index = _token_consume_or_fail(tokens, index, 'BOOL')
    return tok.value == 'true', index

#################### matches null ##########################
def _parse_null(tokens, index):
    tok, index = _token_consume_or_fail(tokens, index, 'NULL')
    return None, index


################################################################################
##### Tokenises an input string ################################################
## results are yielded as a generator
def _tokenize_string(file_string):
    # rules for token types
    token_specification = [
        ('STRING',      r'"(\\.|[^"])*"'),                           # literal strings
        ('NUMBER',      r'[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?'), # literal number (more lax than real json standard)
        ('BOOL',        r'true|false'),                              # true or false
        ('NULL',        r'null'),                                    # just null
        ('PUNCUATION',  r'[{}\[\],:]'),                              # puncuation characters
        ('SLCOMMENT',   r'//[^\n]*'),                                # single-line comment  //
        ('MLCOMMENT',   r'/\*(?:\*[^/]|[^*])*\*/'),                  # multi-line comment  /*  */
        ('NEWLINE',     r'\n'),                                      # newline
        ('WHITESPACE',  r'[^\S\n]+'),                                # whitespace
        ('UNKNOWN',     r'.'),                                       # Any other character
    ]
    # join regexes
    token_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specification)

    line = 1
    column = 1
    # iterate over all the matches
    for mo in re.finditer(token_regex, file_string):
        # get the token name and value
        kind = mo.lastgroup
        value = mo.group(kind)

        # create new token
        yield _colorise_token(kind, value, line, column)

        # compute new line and column
        last_line_length = len(value) - value.rfind('\n') - 1
        column += last_line_length
        if '\n' in value:
            column = last_line_length + 1
        line += value.count('\n')

    # extra special end of file token
    yield _colorise_token('EOF', ' ', line, column)

# class bcolors:
#     BLACK = '\033[30m'
#     RED = '\033[31m'
#     GREEN = '\033[32m'
#     YELLOW = '\033[33m'
#     BLUE = '\033[34m'
#     MAGENTA = '\033[35m'
#     CYAN = '\033[36m'
#     GRAY = '\033[30;1m'
#     LIGHT_GRAY = '\033[37m'
#     WHITE = '\033[37;1m'
#     OKBLUE = '\033[94m'
#     OKGREEN = '\033[92m'
#     WARNING = '\033[93m'
#     FAIL = '\033[91m'
#     BOLD = '\033[1m'
#     UNDERLINE = '\033[4m'
#     ENDC = '\033[0m'

class bcolors:
    BLACK = ''
    RED = ''
    GREEN = ''
    YELLOW = ''
    BLUE = ''
    MAGENTA = ''
    CYAN = ''
    GRAY = ''
    LIGHT_GRAY = ''
    WHITE = ''
    OKBLUE = ''
    OKGREEN = ''
    WARNING = ''
    FAIL = ''
    BOLD = ''
    UNDERLINE = ''
    ENDC = ''

def _colorise_token(type, value, line, column):
    color = bcolors.ENDC + {
        'NUMBER' : bcolors.BLUE,
        'STRING' : bcolors.GREEN,
        'SLCOMMENT' : bcolors.GRAY,
        'MLCOMMENT' : bcolors.GRAY,
        'BOOL' : bcolors.YELLOW,
        'NULL' : bcolors.BLUE,
        'PUNCUATION' : bcolors.WHITE
    }.get(type, bcolors.ENDC);

    if type == 'PUNCUATION':
        type = value

    return Token(type, value, line, column, len(value), color + value)

################################################################################
########  parses a string ######################################################
################################################################################
def loads(file_string, file_source=''):
    global _file_source, _file_lines, _colored_file_lines, _warnings

    _warnings = []
    _file_source = file_source

    file_string = file_string.rstrip('\n')
    _file_lines = file_string.splitlines()
    file_string = '\n'.join(_file_lines)

    try:
        tokens = list(_tokenize_string(file_string))

        # get preview line again, but this time after colorising the tokens
        _colored_file_lines = (''.join(map(lambda tok: tok.cvalue, tokens)) + bcolors.ENDC).splitlines()

        # import pdb; pdb.set_trace()
        obj, index = _parse_value(tokens)

        _token_consume_or_fail(tokens, index, 'EOF')

        # check to make sure we have either an object or array as the root value
        if not isinstance(obj, dict) and not isinstance(obj, list):
            raise TypeError('Root level value must be object or array.')

        # comment for comment symmetry
        return obj, _warnings
    except TypeError as e:

        return {}, _warnings + [str(e)]

def pretty_print():
    print ('\n'.join(_colored_file_lines))

def loadf(filename):
    with open(filename,'r',encoding='utf8') as f:
        return load(f)

##### Parse file instead of string #############################################
def load(f):
    try:
        return json.load(f, object_pairs_hook=collections.OrderedDict), []
    except json.JSONDecodeError:
        f.seek(0)
        return loads(f.read(), f.name)
###############################################################################

################ Dumping json objects
from decimal import Decimal
class _fake_float(float):
    def __init__(self, value):
        self._value = value
    def __repr__(self):
        d = self._value
        d = d.quantize(Decimal('1.')) if d == d.to_integral() else d.normalize()
        return str(d)
def _json_encoder_default_handler(o):
    if isinstance(o, Decimal):
        return _fake_float(o)
    raise TypeError(repr(o) + ' is not JSON serializable')

def dump(obj, file, **kwargs):
    return json.dump(obj, file, default=_json_encoder_default_handler, **kwargs)

def dumps(obj, file, **kwargs):
    return json.dumps(obj, default=_json_encoder_default_handler, **kwargs)


# import sys
# import loader

# def main():
#     if len(sys.argv) == 1:
#         infile = sys.stdin
#         outfile = sys.stdout
#     elif len(sys.argv) == 2:
#         infile = open(sys.argv[1], 'r')
#         outfile = sys.stdout
#     elif len(sys.argv) == 3:
#         infile = open(sys.argv[1], 'r')
#         outfile = open(sys.argv[2], 'w')
#     else:
#         raise SystemExit(sys.argv[0] + " [infile [outfile]]")
#     with infile:
#         try:
#             obj = load(infile)
#         except ValueError as e:
#             raise SystemExit(e)
#     with outfile:
#         if outfile == sys.stdout:
#             loads(loader.dumps(obj, indent=4, separators=(',', ': ')))
#             pretty_print()
#         else:
#             loader.dump(obj, outfile, indent=4, separators=(',', ': '))
#             outfile.write('\n')

# if __name__ == '__main__':
#     main()
