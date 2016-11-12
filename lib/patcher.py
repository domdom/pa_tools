import decimal
import collections
import re
import copy
import numbers
from collections import OrderedDict

RE_ARRAY_INDEX=re.compile('0|[1-9][0-9]*$')

############################################################
### error cases and their exceptions #######################
############################################################
class JsonPatchError(Exception):
    def __init__(self, name, message, operation, doc):
        self.name = name
        self.message = message
        self.operation = operation
        self.doc = doc
        super(JsonPatchError, self).__init__(message)

class JsonTestError(Exception):
    def __init__(self, name, message, operation, doc):
        self.name = name
        self.message = message
        self.operation = operation
        self.doc = doc
        super(JsonTestError, self).__init__(message)

# short hand for these errors
def _ERROR_NO_KEY(key, partial_path, obj):
    return JsonPatchError('ERROR_INVALID_OBJECT_INDEX', 'Error: key %r is not defined in object located at %r.' % (key, partial_path), None, obj)
def _ERROR_ARRAY_NO_SPECIAL(key, path_str, obj):
    return JsonPatchError('ERROR_INVALID_ARRAY_INDEX', 'Error: special %r array index value can only appear as the last component of a json pointer. %r.' % (key, path_str), None, obj)
def _ERROR_ARRAY_OUT_OF_BOUNDS(key, partial_path, obj):
    return JsonPatchError('ERROR_INVALID_ARRAY_INDEX', 'Error: array index %r is out of bounds for array at %r.' % (key, partial_path), None, obj)
def _ERROR_ARRAY_INVALID_INDEX(key, partial_path, obj):
    return JsonPatchError('ERROR_INVALID_ARRAY_INDEX', 'Error: failed to parse %r as an int for path %r.' % (key, partial_path), None, obj)
def _ERROR_NOT_INDEXABLE(key, partial_path, obj):
    return JsonPatchError('ERROR_NOT_INDEXABLE', 'Error: value at %r is of type %r and is not valid for an index operation.' % (partial_path, type(obj).__name__), None, obj)

def _ERROR_TEST_FAILED(operation, obj):
    return JsonPatchError('ERROR_TEST_FAILED', 'Error: test failed.', operation, obj)

def _ERROR_INVALID_OPERATION(operation):
    return JsonPatchError('ERROR_INVALID_OPERATION', 'Error: %r is not a valid operation.' % operation['op'])

# create patch object from the diff of two objects
def from_diff(a, b):
    def _compare(l, r, path=[]):
        if type(l) != type(r):
            yield OrderedDict([
                    ('op', 'replace'),
                    ('path', _encode_path(path)),
                    ('value', r)
                ])
        # the types must be the same!
        # check the type
        elif isinstance(l, dict):
            # we have a dictionary
            # check for removed items
            for k in l:
                if k not in r:
                    # found a key in l, that is not in r
                    yield OrderedDict([
                            ('op', 'remove'),
                            ('path', _encode_path(path + [k])),
                            ('value', l[k]),
                            ('_type', 'dict')
                        ])
                else:
                    for operation in _compare(l[k], r[k], path + [k]):
                        yield operation

            # check for added items
            for k in r:
                if k not in l:
                    # found a key in r, that is not in l
                    yield OrderedDict([
                            ('op', 'add'),
                            ('path', _encode_path(path + [k])),
                            ('value', r[k]),
                            ('_type', 'dict')
                        ])
                # we don't need to deal with elements that are the same, treated in previous for loop
        # we have a list, this means we need to invoke our lcs implementation to find minimal edits
        elif isinstance(l, list):
            list_operations = _optimize_list_patches(list(_longest_common_subseq(l, r, path)))
            for operation in list_operations:
                yield operation
        # we have some basic values, do direct comparison
        # can be either some number, bool, or string
        elif l != r:
            yield OrderedDict([
                    ('op', 'replace'),
                    ('path', _encode_path(path)),
                    ('value', r)
                ])

    patches = _optimize_patches(list(_compare(a, b)))
    # do optimisation here
    return patches

# find the longest matching sequence in two arrays
# (the matching elements must match perfectly)
def _longest_common_subseq(a, b, path):
    lengths = [[0 for j in range(len(b)+1)] for i in range(len(a)+1)]
    # row 0 and column 0 are initialized to 0 already
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            if x == y:
                lengths[i+1][j+1] = lengths[i][j] + 1
            else:
                lengths[i+1][j+1] = \
                    max(lengths[i+1][j], lengths[i][j+1])
    # read the substring out from the matrix
    x, y = len(a), len(b)
    # while we have more to check
    while x != 0 and y != 0:
        if lengths[x][y] == lengths[x-1][y]:
            x -= 1
            yield OrderedDict([
                    ('op', 'remove'),
                    ('path', _encode_path(path + [x])),
                    ('value', a[x]),
                    ('_type', 'list')
                ])
        elif lengths[x][y] == lengths[x][y-1]:
            y -= 1
            yield OrderedDict([
                    ('op', 'add'),
                    ('path', _encode_path(path + [x])),
                    ('value', b[y]),
                    ('_type', 'list')
                ])
        else:
            x -= 1
            y -= 1

    while x != 0:
            x -= 1
            yield OrderedDict([
                    ('op', 'remove'),
                    ('path', _encode_path(path + [x])),
                    ('value', a[x]),
                    ('_type', 'list')
                ])

    while y != 0:
            y -= 1
            yield OrderedDict([
                    ('op', 'add'),
                    ('path', _encode_path(path + [x])),
                    ('value', b[y]),
                    ('_type', 'list')
                ])

###################################################################
# Application of patches ##########################################
###################################################################

# apply patch to object and return new object
def apply_patch(obj, patches, custom_ops={}):
    global _custom_op_methods
    _custom_op_methods = custom_ops
    # method names
    # make copy
    obj = copy.deepcopy(obj)

    for operation in patches:
        # check for invalid operation
        _validate_operation(obj, operation)

        if operation["op"] in _op_methods:
            op_table = _op_methods
        if operation["op"] in _custom_op_methods:
            op_table = _custom_op_methods

        obj = op_table[operation["op"]](obj, operation)
    return obj
# tries to optimize the list of patches so that
# add / remove patches are combined where possible
def _optimize_list_patches(patches):
    # TODO: currently noop
    return patches
# tries to optimize all the patches that are not inside lists (by checkign the _type field)
def _optimize_patches(patches):
    # TODO: currently noop
    return _clean_patches(patches)
# removes extra data
def _clean_patches(patches):
    # remove unneeded values from patches
    for operation in patches:
        operation.pop('_type', None)

        # remove op should not have 'value'
        if operation['op'] in ['remove', 'move', 'copy']:
            operation.pop('value', None)

    return patches

###################################################################
# Patch operation validation ######################################
###################################################################

# fully validates an operation given the current state
# throws exeptions as required
def _validate_operation(doc, operation):
    if "op" in operation and operation["op"] in _custom_op_methods:
        return
    if "op" not in operation or operation["op"] not in _op_methods:
        raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation type %r is not defined.' % operation['op'], operation, doc)
    if operation['op'] not in []:
        if 'path' not in operation:
            raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation type %r must have a \'path\' member.' % operation['op'], operation, doc)
    if operation['op'] not in ['remove', 'move', 'copy']:
        if 'value' not in operation:
            raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation type %r must have a \'value\' member.' % operation['op'], operation, doc)
    if operation['op'] in ['move', 'copy']:
        if 'from' not in operation:
            raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation type %r must have a \'from\' member.' % operation['op'], operation, doc)

    # check paths
    if operation['op'] in ['add', 'move', 'copy']:
        path = _decode_path(operation['path'])
        # these operations don't need the last key to exist
        _validate_path_available(doc, path)
    else:
        path = _decode_path(operation['path'])
        # the last key value must exist
        _validate_path_exists(doc, path)

    if operation['op'] in ['move', 'copy']:
        path = _decode_path(operation['from'])
        _validate_path_exists(doc, path)

    # verify value types
    #  - scale, offset
    if operation['op'] in ['scale', 'offset']:
        if not isinstance(operation['value'], (numbers.Real, decimal.Decimal)):
            raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation type %r must have a numeric \'value\' argument.' % operation['op'], operation, doc)
        subdoc, key = _ptr(doc, operation['path'])
        if not isinstance(subdoc[key], (numbers.Real, decimal.Decimal)):
            raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation type %r must have a numeric value at \'path\'.' % operation['op'], operation, doc)

    if operation['op'] in ['test_lt', 'test_lte', 'test_gt', 'test_gte']:
        raise JsonPatchError('ERROR_UNIMPLEMENTED_OPERATION', 'Operation type %r has not been implemented yet. Bug dom314 if you need this.' % operation['op'], operation, doc)
        #if not isinstance(operation['value'], numbers.Real) or not isinstance(operation['value'], str):
            #raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation type %r must have a numeric or string \'value\' argument.' % operation['op'], operation, doc)
        #subdoc, key = _ptr(doc, operation['path'])
        #if not isinstance(subdoc[key], numbers.Real) or not isinstance(subdoc[key], str):
            #raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation type %r must have a numeric or string value at \'path\'.' % operation['op'], operation, doc)
        #if type(operation['value']) != type(subdoc[key]):
            #raise JsonPatchError('ERROR_INVALID_OPERATION', 'Operation \'value\' and json value at %r must be of the same type.' % operation['op'], operation, doc)

# validates that a path exists, all the way to the last path fragment
def _validate_path_exists(doc, path):
    # if path is empty, we are dealing with root
    if not path: return doc, None
    # iterate to get last sub-object and key
    for i, key in enumerate(path[:-1]):
        key = _validate_key_exists(doc, key, _encode_path(path[:i]))
        doc = doc[key]
    return doc, _validate_key_exists(doc, path[-1], _encode_path(path[:-1]))

# validates that a path exists, and checks the last fragment is available for insertion
def _validate_path_available(doc, path):
    # if path is empty, we are dealing with root
    if not path: return doc, None
    # check path exists up until last path fragment
    doc, key = _validate_path_exists(doc, path[:-1])

    # make sure we have key to use
    if key != None:
        doc = doc[key]

    # because of above check, we know we can do this
    return doc, _validate_key_available(doc, path[-1], _encode_path(path[:-1]))

# checks if key fragment is available
def _validate_key_exists(obj, key, partial_path):
    if isinstance(obj, dict):
        if key in obj:
            return key
        raise _ERROR_NO_KEY(key, partial_path, obj)
    elif isinstance(obj, list):
        if key == '-':
            raise _ERROR_ARRAY_NO_SPECIAL(key, path_str, obj)
        elif RE_ARRAY_INDEX.match(key):
            try:
                key = int(key)
                if key < len(obj) and key >= 0:
                    return key
                raise _ERROR_ARRAY_OUT_OF_BOUNDS(key, partial_path, obj)
            except ValueError:
                raise _ERROR_ARRAY_INVALID_INDEX(key, partial_path, obj)
    raise _ERROR_NOT_INDEXABLE(key, partial_path, obj)

# check if key fragment is available for insertion
def _validate_key_available(obj, key, partial_path):
    if isinstance(obj, dict):
        return key
    elif isinstance(obj, list):
        if key == '-':
            return len(obj)
        elif RE_ARRAY_INDEX.match(key):
            try:
                key = int(key)
                if key <= len(obj) and key >= 0:
                    return key
                raise _ERROR_ARRAY_OUT_OF_BOUNDS(key, partial_path, obj)
            except ValueError:
                raise _ERROR_ARRAY_INVALID_INDEX(key, partial_path, obj)
    raise _ERROR_NOT_INDEXABLE(key, partial_path, obj)

# resolves a json pointer (assumes already validated)
def _ptr(obj, path_str):
    path = _decode_path(path_str)
    # this method formats the next key
    def _key(obj, key, partial_path=None):
        if isinstance(obj, dict):
            return key
        elif isinstance(obj, list):
            if key == '-':
                return len(obj)
            else:
                return int(key)
    # doc will be the sub-object returned along with the last key
    doc = obj
    # if path is empty, we are dealing with root
    if not path: return doc, None
    # iterate to get last sub-object and key
    for i, key in enumerate(path[:-1]):
        doc = doc[_key(doc, key)]
    return doc, _key(doc, path[-1])

######################################################################
## Operation functions ###############################################
######################################################################
def _op_not_implemented(obj, operation):
    # this is the not implemented operation
    print(('WARNING: %s is not yet implemented' % operation['op']))
    return obj
# add operation
def _op_add(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if key == None:
        return operation['value']

    if isinstance(doc, list):
        doc.insert(key, operation['value'])
    else:
        doc[key] = operation['value']

    return obj

# remove operation
def _op_remove(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if isinstance(doc, list):
        del doc[key]
    elif isinstance(doc, dict):
        doc.pop(key, None)
    return obj

# remove operation
def _op_replace(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if key == None:
        return operation['value']
    doc[key] = operation['value']
    return obj

def _op_move(obj, operation):
    from_path = operation['from']
    to_path = operation['path']
    doc, key = _ptr(obj, from_path)
    value = doc[key]
    obj = _op_remove(obj, {"op" : "remove", "path" : from_path})
    return _op_add(obj, {"op" : "add", "path" : to_path, "value" : value})

def _op_copy(obj, operation):
    from_path = operation['from']
    to_path = operation['path']
    doc, key = _ptr(obj, from_path)
    value = doc[key]
    return _op_add(obj, {"op" : "add", "path" : to_path, "value" : copy.deepcopy(value)})

# testing values, the whole thing dies if a test fails
def _op_test(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if key != None:
        doc = doc[key]
    if doc != operation['value']:
        raise JsonTestError('ERROR_TEST_FAILED', 'Test failed', operation, obj)

    return obj

def _op_test_not_eq(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if key != None:
        doc = doc[key]
    if doc == operation['value']:
        raise JsonTestError('ERROR_TEST_FAILED', 'Test failed', operation, obj)

    return obj

# scales number values
def _op_scale(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if key == None:
        return doc * operation['value']
    doc[key] *= operation['value']
    return obj

# offsets number values
def _op_offset(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if key == None:
        return doc + operation['value']
    doc[key] += operation['value']
    return obj

## not yet implemented
def _op_test_in(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if key != None:
        doc = doc[key]
    if operation['value'] not in doc:
        raise JsonTestError('ERROR_TEST_FAILED', 'Test failed', operation, obj)
    return obj

def _op_test_not_in(obj, operation):
    doc, key = _ptr(obj, operation['path'])
    if key != None:
        doc = doc[key]
    if operation['value'] in doc:
        raise JsonTestError('ERROR_TEST_FAILED', 'Test failed', operation, obj)
    return obj

###################################
def _op_test_lt(obj, operation):
    return _op_not_implemented(obj, operation)
def _op_test_lte(obj, operation):
    return _op_not_implemented(obj, operation)
def _op_test_gt(obj, operation):
    return _op_not_implemented(obj, operation)
def _op_test_gte(obj, operation):
    return _op_not_implemented(obj, operation)

_op_methods = {
    # standard compliant operations
    "add"           : _op_add,
    "remove"        : _op_remove,
    "replace"       : _op_replace,
    "move"          : _op_move,
    "copy"          : _op_copy,
    "test"          : _op_test,
    # extensions
    "scale"         : _op_scale,
    "offset"        : _op_offset,
    "test_eq"       : _op_test, # identical to 'test'
    "test_not_eq"   : _op_test_not_eq, # returns true if not equal
    "test_in"       : _op_test_in, # like the python 'in' operator (for object, test if key is defined, for array, if array contains)
    "test_not_in"   : _op_test_not_in, # like the python 'not in' operator
    "test_lt"       : _op_test_lt, # less than
    "test_lte"      : _op_test_lte, # less than or equal to
    "test_gt"       : _op_test_gt, # greater than
    "test_gte"      : _op_test_gte # greater than or equal to
}

# a list of custom op handlers
_custom_op_methods = {}
############################################
############################################
# return json pointer encoded string
def _encode_path(path):
    path = [str(item) for item in path]
    path = [item.replace('~', '~0') for item in path]
    path = [item.replace('/', '~1') for item in path]
    return ''.join(['/' + part for part in path])

# return path
def _decode_path(str_path):
    # refering to the root of the document
    if str_path == '': return []

    path = str_path[1:].split('/')
    path = [item.replace('~1', '/') for item in path]
    path = [item.replace('~0', '~') for item in path]
    return path

########################################################
##### Testing stuff ####################################
########################################################
def _tester():
    print("##################################################")
    print("Testing with 'tests.json'")
    print("##################################################")
    import json
    
    tests = json.load(open('tests.json'))

    for test in tests:
        if 'comment' in test:
            print(test['comment'])

        try:
            if 'error' in test:
                try:
                    apply_patch(test['doc'], test['patch'])
                except Exception as es:
                    print('    \t\t\t\t\tpass!')

            elif 'doc' in test:
                if 'expected' in test:
                    if apply_patch(test['doc'], test['patch']) == test['expected']:
                        print('   \t\t\t\t\tpass!')
                    else:
                        print('***\t\t\t\t\tfail! - not same value')
                else:
                    # all we are expection is not to get an exception
                    apply_patch(test['doc'], test['patch'])
                    print('   \t\t\t\t\tpass!')
        except Exception as ex:
            print('***\t\t\t\t\tfail! - uncaught exception')
            print(ex)

    print("##################################################")
    print("Testing diff method for idempotency")
    print("##################################################")
    for test in tests:
        if 'doc' not in test or 'expected' not in test or 'patch' not in test or 'error' in test:
            continue

        if 'comment' in test:
            print(test['comment'])

        try:
            doc = test['doc']
            expected = test['expected']

            patch = from_diff(doc, expected)

            if expected == apply_patch(doc, patch):
                print('   \t\t\t\t\tpass!')
            else:
                print('***\t\t\t\t\tfail! - patch is wrong!')
                print(json.dumps(doc, indent=2))
                print(json.dumps(expected, indent=2))
                print(json.dumps(patch, indent=2))


        except JsonPatchError as ex:
            print('***\t\t\t\t\tfail! - uncaught exception')
            print(ex)

if __name__ == '__main__':
    _tester()
