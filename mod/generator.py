#!/usr/bin/env python3
from datetime import datetime
from shutil import copyfile
import collections
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
                print ("\n!! ERROR: Not Found '" + change['from_file'] + "'\n")
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
            destinations = change.get('destination', target)

            # but potentially multiple destinations
            if isinstance(destinations, str):
                destinations = [destinations]

            for destination in destinations:
                _do_patch(target, change['patch'], destination, loader, out_dir)


        # list of targets
        if isinstance(change['target'], list):
            for target in change['target']:
                _do_patch(target, change['patch'], target, loader, out_dir)


def process_modinfo(modinfo_path, loader, out_dir):
    print('======= Loading Modinfo =======')

    resolved = loader.resolveFile(modinfo_path)
    base_modinfo, warnings = pajson.loadf(resolved)
    for w in warnings:
        print(w)

    modinfo = update_modinfo(base_modinfo)

    print('identifier:', modinfo['identifier'])
    print('     build:', modinfo['build'])
    print('-------------------------------')

    destination_path = _join(out_dir, 'modinfo.json')
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    with open(destination_path, 'w', newline='\n') as dest:
        pajson.dump(modinfo, dest, indent=2)

def update_modinfo(base_modinfo):
    modinfo = collections.OrderedDict([
        ('identifier', 'no.mod.info.supplied'),
        ('context', 'client')]
    )
    modinfo.update(base_modinfo)
    modinfo['build'] = str(PA_VERSION)
    modinfo['date'] = datetime.utcnow().strftime("%Y-%m-%d")
    modinfo['signature'] = modinfo.get('signature', ' ')
    return modinfo
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
        print ("\n!! ERROR: Not Found '" + target + "'")
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

    custom_ops = {
        'scale_effect' : _scale_effect_handler
    }

    result_obj = patcher.apply_patch(target_obj, patch, custom_ops)

    with open(destination_path, 'w', newline='\n') as dest:
        pajson.dump(result_obj, dest, indent=2)

###################################### patcher extensions ##############################
def _scale_effect_handler(obj, operation):
    to_scale = [
        'sizeX', 'sizeY',
        'sizeRangeX', 'sizeRangeY',
        'velocity', 'velocityRange',
        'offsetX', 'offsetY', 'offsetZ',
        'offsetRangeX', 'offsetRangeY', 'offsetRangeZ',
        'accelX', 'accelY', 'accelZ',

        'gravity',
        'snapToSurfaceOffset'
    ]

    scale = operation["value"]

    for i, emitter in enumerate(obj['emitters']):
        for key in to_scale:
            if key in emitter:
                try:
                    if isinstance(emitter[key], (float, int)):
                        obj['emitters'][i][key] *= scale
                    elif isinstance(emitter[key], list):
                        for j, value in enumerate(emitter[key]):
                            obj['emitters'][i][key][j][1] *= scale
                    elif isinstance(emitter[key], dict):
                        for j, value in enumerate(emitter[key]['keys']):
                            obj['emitters'][i][key]['keys'][j][1] *= scale
                    else:
                        print('Unexpected "' + key + '" formet:', emitter[key])
                except:
                    print('Exception:', key, obj['emitters'][i][key])
                    raise
    return obj