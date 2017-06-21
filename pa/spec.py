from pa_tools.pa import pajson

import copy

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

    return spec

def parse_spec(loader, file_path):
    # do cache lookup first
    if file_path in _cache:
        return _cache[file_path]

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

def clear_cache():
    global _cache
    _cache = {}