from pa_tools.pa import pajson

import copy

def _has_key_sequence(obj, keys):
    for key in keys:
        if key not in obj:
            return False
        
        obj = obj[key]
    
    return True

_cache = {}
def update_spec(spec, base_spec):
    spec = copy.deepcopy(spec)
    for key, value in base_spec.items():
        if key not in spec:
            spec[key] = value
        elif key in spec and isinstance(spec[key], dict) and isinstance(value, dict):
            spec[key] = update_spec(spec[key], value)

    return spec


def prune_spec(spec, base_spec):
    spec = copy.deepcopy(spec)
    spec_keys = list(spec.keys() & base_spec.keys())
    for key in spec_keys:
        if key in base_spec:
            if spec[key] == base_spec[key]:
                del spec[key]
            elif isinstance(spec[key], dict) and isinstance(base_spec[key], dict):
                spec[key] = prune_spec(spec[key], base_spec[key])
                if spec[key] == {}:
                    del spec[key]

    return spec

def find_def(loader, file_path, keys):
    resolved_file_path = loader.resolveFile(file_path)

    if resolved_file_path == None:
        return None


    spec, warnings = pajson.loadf(resolved_file_path)
    
    # If this spec has the key, then we are done
    if _has_key_sequence(spec, keys):
        return file_path
    

    # If not, we have to check the base spec
    base_spec_id = spec.get('base_spec', None)
    if base_spec_id:
        return find_def(loader, base_spec_id, keys)

    return None


def parse_spec(loader, file_path):
    # do cache lookup first
    if file_path in _cache:
        return copy.deepcopy(_cache[file_path])

    resolved_file_path = loader.resolveFile(file_path)

    if resolved_file_path == None:
        return None


    spec, warnings = pajson.loadf(resolved_file_path)
    base_spec_id = spec.get('base_spec', None)
    if base_spec_id:
        base_spec = parse_spec(loader, base_spec_id)
        spec = update_spec(spec, base_spec)

    _cache[file_path] = spec
    return copy.deepcopy(spec)

def load_spec(loader, file_path):
    resolved_file_path = loader.resolveFile(file_path)
    if resolved_file_path is None:
        loader.resolveFile(file_path, True)

    spec, warnings = pajson.loadf(resolved_file_path)
    list(map(print, warnings))
    return spec

def clear_cache():
    global _cache
    _cache = {}