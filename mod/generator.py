#!/usr/bin/env python3
from datetime import datetime
from shutil import copyfile
import os

from pa_tools.lib import patcher
from pa_tools.pa import pajson
from pa_tools.pa.paths import PA_MEDIA_DIR
from pa_tools.pa.paths import PA_VERSION

#####################################
# Public Methods
#####################################
def process_changes(changes, loader, out_dir):
    for change in changes:
        # we have an object, but it is a reference to a file patch to load
        if isinstance(change, dict) and 'from_file' in change:
            from_file = loader.resolveFile(change['from_file'])

            if from_file == None:
                print ("!! ERROR: Not Found '" + change['from_file'] + "'")
                continue

            print('==== loading:', from_file)
            changes, warnings = pajson.loadf(from_file)

            for w in warnings:
                print(w)
            # make sure our changes are a list
            if isinstance(changes, dict):
                changes = [changes]

            # process new list recursively.
            from os.path import dirname
            loader.mount('/', dirname(from_file))
            process_changes(changes, loader, out_dir)
            loader.unmount('/')

            continue

        # implicit patch
        if 'patch' not in change:
            change['patch'] = []

        # we have a single target
        if isinstance(change['target'], str):
            target = change['target']
            destination = change.get('destination', target)

            _do_patch(target, change['patch'], destination, loader, out_dir)

        # list of targets
        if isinstance(change['target'], list):
            for target in change['target']:
                _do_patch(target, change['patch'], target, loader, out_dir)

#####################################
# Helper Methods
#####################################
# joins to paths, but first removes a leading slash
def _join(path1, path2):
    from posixpath import join
    if path1 is None or path2 is None:
        return None
    return join(path1, path2.strip("/"))

# do the actual patch, or copy operation, as it may be
def _do_patch(target, patch, destination, loader, out_dir):
    resolved = loader.resolveFile(target)
    if resolved == None:
        print ("!! ERROR: Not Found '" + target + "'")
        return

    destination_path = _join(out_dir, destination)
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)

    if patch == []:
        print (' copy: ' + destination_path)
        copyfile(resolved, destination_path)
        return

    print ('patch: ' + destination_path)
    target_obj, warnings = pajson.loadf(resolved)

    for w in warnings:
        print(w)

    result_obj = patcher.apply_patch(target_obj, patch)

    with open(destination_path, 'w') as dest:
        pajson.dump(result_obj, dest)

def generate_modinfo(base_modinfo):
    modinfo = {
        'identifier' : 'no.mod.info.supplied',
        'context' : 'client'
    }

    modinfo.update(base_modinfo)

    modinfo['build'] = str(PA_VERSION)
    modinfo['date'] = datetime.utcnow().strftime("%Y-%m-%d")
    modinfo['signature'] = modinfo.get('signature', ' ')

    return modinfo
