#!/usr/bin/env python3
import collections
import time
from datetime import datetime
import sys
import os

from pa_tools.lib import patcher
from pa_tools.pa.paths import PA_MEDIA_DIR
from pa_tools.pa.paths import PA_VERSION

# initialise some global vars
_options = {}
_pa_dir = ''
_mod_dir = ''
_backup_dir = ''

# collect all the files that are going to be stored
# so that we can condense patches
_patch_buffer = collections.OrderedDict()


def _process_changes(dirs, changes):
    # loader.print_json(changes, indent=2)
    for change in changes:
        # we have an object, but it is a reference to a file patch to load
        if isinstance(change, dict) and 'from_file' in change:
            from_file = _get_source_file_path(change['from_file'], dirs)

            print('Loading patch file:', from_file)
            changes = loader.load(from_file)
            # make sure our changes are a list
            if isinstance(changes, dict):
                changes = [changes]
            # process new list recursively.
            _process_changes([os.path.dirname(from_file)] + dirs, changes)
            continue

        # if we need to run a script first...
        if isinstance(change, dict) and 'from_script' in change:
            from_script = _get_source_file_path(change['from_script'], dirs)


            script_scope = {}
            print('Running python script:', from_script)

            old_cwd = os.getcwd()

            script_module = compile(open(from_script, "rb").read(), from_script, 'exec')
            # change dirs into the script's location so that relative paths work
            os.chdir(os.path.dirname(from_script))
            exec(script_module, script_scope)

            patches = []
            # check if the script has a run method, if so, run that
            if 'run' in script_scope:
                patches = script_scope['run']()
                if isinstance(patches, dict):
                    patches = [patches]

            # restore old working directory
            os.chdir(old_cwd)

            if patches:
                _process_changes([os.path.dirname(from_script)] + dirs, patches)


            continue

        # implicit patch
        if 'patch' not in change:
            change['patch'] = []

        # implicit target (all units in unit_list.json)
        if 'target' not in change:
            # compute targets from unit_list.json
            change['target'] = []
            unit_list = loader.load(os.path.join(_pa_dir, 'pa/units/unit_list.json'))
            change['target'] = unit_list['units']

        # we have a single target
        if isinstance(change['target'], str):
            target = change['target']
            destination = change.get('destination', target)

            _add_patch_job(target, change['patch'], destination, dirs)

        # list of targets
        if isinstance(change['target'], list):
            for target in change['target']:
                _add_patch_job(target, change['patch'], target, dirs)

# process a mod file
# needs resolved paths for pa_dir and mod_dir
def process_mod(mod_data):
    global _options
    global _mod_dir
    global _pa_dir
    # parse the options
    # debug mode : copy modded files directly to the pa_base game files
    _options['debug_mode'] = mod_data.get('options', {}).get('debug_mode', False)
    # output dir : defaults to the pa mods directory,
    # override to generate in another location
    _options['output_dir'] = mod_data.get('options', {}).get('output_dir', None)
    # pretty print options - choose indent level
    _options['indent'] = mod_data.get('options', {}).get('indent', None)

    # check if we are targeting the pa titans expansion or not
    _options['target_expansion'] = mod_data.get('options', {}).get('target_expansion', False)

    # this option controls whether or not targets with the path /pa/ tries to look for a /pa_ex1/ path instead
    _options['prefer_ex1'] = mod_data.get('options', {}).get('prefer_ex1', False)

    # check if I want effect files to be specially pretty printed
    _options['pretty_print_effects'] = mod_data.get('options', {}).get('pretty_print_effects', False)
    # this needs another option besides indent since effect files I like to have printed a bit differently
    # effect files have a very regular structure; arrays that appear inside the emitter and particle spec usually pertain to a single property
    # using time curves. If there are a lot of elements in these arrays, the default indentation behaviour for json files will
    # add lots of lines which are unnecessary without adding to the readibility of the file. Basically, only objects have special indentation
    # arrays are not indented after the shallowest one containing the emitters.

    # when I add validation
    _validate_mod(mod_data)

    modinfo = mod_data.get('modinfo', {
        'identifier' : 'no.mod.info.supplied',
        'context' : 'client'
        })

    modinfo['build'] = str(utils.pa_build())
    modinfo['date'] = datetime.utcnow().strftime("%Y-%m-%d")
    modinfo['signature'] = modinfo.get('signature', ' ')

    mod = mod_data.get('mod', [])


    # this is the default location to place generated files (based on identity and mod context)
    mod_dest_dir = os.path.join(utils.pa_data_dir(), modinfo['context'] + '_mods', modinfo['identifier'])
    # if we have set another folder, use that
    if _options['output_dir']:
        mod_dest_dir = os.path.join(_mod_dir, _options['output_dir'])

    # change working dir, so that relative paths for mod_dest will work

    if _options['debug_mode']:
        mod_dest_dir = _pa_dir

    print ('-' * 100)
    _process_changes([_mod_dir, _backup_dir, _pa_dir], mod)
    _flush_jobs(mod_dest_dir)

    loader.dump(modinfo, os.path.join(mod_dest_dir, 'modinfo.json'), indent=4)

def _add_patch_job(target, patch, dest, dirs):
    path = _get_source_file_path(target, dirs)
    if path == None:
        print ('Could not find the file', target)
    else:
        key = path, dest
        arr = _patch_buffer.pop(key, [])
        _patch_buffer[key] = arr + [patch]

def _flush_jobs(mod_dest_dir):
    print ('-' * 100)
    print ('Writing files to', mod_dest_dir)
    print ('-' * 100)
    for k in _patch_buffer:

        patches = [_f for _f in _patch_buffer[k] if _f]

        from_path = k[0]
        to_path = _get_destination_path(k[1], mod_dest_dir)

        # here we need to check to see if we are writing to the base game files
        #    and then make a backup if we are
        if _options['debug_mode']:
            backup_path = _get_destination_path(k[1], _backup_dir)
            if os.path.isfile(to_path) and not os.path.isfile(backup_path):
                print('File already exists, making backup:' + to_path)
                loader.copy(to_path, backup_path)


        # if there is no patch to apply, just copy files
        if not patches:
            print('Copying ', k[1])
            loader.copy(from_path, to_path)
            continue

        # only bother parsing as json if there are patches to apply
        obj_old = loader.load(from_path)
        obj_new = obj_old


        for patch in patches:
            # apply patch and save
            try:
                obj_new = patcher.apply_patch(obj_new, patch)
            except patcher.JsonTestError:
                # print(from_path + ' failed a test. ignoring.')
                continue
            except patcher.JsonPatchError as e:
                print(e)
                print(loader.dumps(e.doc, indent=2))
                raise

        # skip if no patches were applied (or were idempotent)
        if obj_new == obj_old:
            # print("No patches applied to file, skipping:", k[1])
            continue
        # if the destination file exists, check to make sure we actually have
        # value to write
        if os.path.isfile(to_path):
            obj_old = loader.load(to_path)
            # no changes to make, skip update
            if obj_old == obj_new:
                print("==", k[1])
                continue


        print('++', k[1])
        if _options['pretty_print_effects'] and to_path.endswith('.pfx'):
            # we have an effect file, so pretty print
            loader.dump_effect(obj_new, to_path)
            pass
        else:
            # normal json, try to print as normal
            loader.dump(obj_new, to_path, indent=_options['indent'])

def _get_source_file_path(target, dirs):
    # take away initial slash

    if target[0] == "/":
        target = target[1:]

    if target.startswith("pa/"):
        if _options['prefer_ex1']:
            ex1_path = _get_source_file_path('pa_ex1' + target[2:], dirs)
            if ex1_path:
                return ex1_path

    for d in dirs:
        path = os.path.join(d, target)
        if os.path.isfile(path):
            return path
    return None

def _get_destination_path(target, mod_dest_dir):
    # take away initial slash
    if target[0] == "/":
        target = target[1:]

    if target.startswith("pa/"):
        if _options['prefer_ex1'] and _options['debug_mode']:
            ex1_path = os.path.join(mod_dest_dir, 'pa_ex1' + target[2:])
            if os.path.exists(ex1_path):
                target = 'pa_ex1' + target[2:]

    return os.path.join(mod_dest_dir, target)

def _validate_mod(mod):
    print("Ummmm...not being validated yet. Just passing for free now xD")
    pass
    
def _pa_build():
    pa_version = os.path.normpath(os.path.join(PA_MEDIA_DIR, '..', 'version.txt'))

    with open(pa_version) as version:
        return version.readline().strip()

def run(path):
    global _mod_dir, _pa_dir, _backup_dir
    mod_data_path = path

    try:
        mod_data = loader.load(mod_data_path)
    except Exception as e:
        print(e)
    else:
        _mod_dir = os.path.dirname(mod_data_path)
        _pa_dir = utils.pa_media_dir()
        _backup_dir = os.path.join(_pa_dir, '../_media')

        print ('mod dir:', _mod_dir)
        print ('pa  dir:', _pa_dir)
        print ('back up dir:', os.path.normpath(_backup_dir))

        # we have all the information we need, process the mod!
        # process the mod
        process_mod(mod_data)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(sys.argv[0] + ' takes one argument, the path to the .json file describing the mod')
    elif not os.path.isfile(sys.argv[1]):
        print(sys.argv[1] + ' is not a file')
    else:
        run(sys.argv[1])

