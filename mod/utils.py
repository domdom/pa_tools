import os
import shutil
import contextlib

from pa_tools.pa import pafs
from pa_tools.pa import paths
from pa_tools.pa import pajson


def create_pafs(is_titans=True):
    src = pafs(paths.PA_MEDIA_DIR)

    src.mount('/pa/', paths.PA_MEDIA_DIR + '/backup/pa')
    if is_titans:
        src.mount('/pa/', '/pa_ex1')
        src.mount('/pa/', paths.PA_MEDIA_DIR + '/backup/pa_ex1')

    return src


def _join(path1, path2):
    if path1 is None or path2 is None:
        return None
    return os.path.join(path1, path2.strip("/"))

def _copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)

def deploy_debug(mod_dir):
    backup_path = paths.PA_MEDIA_DIR + '/backup'
    print('Creating backup directory', backup_path)
    os.makedirs(backup_path, exist_ok=True)

    src = pafs(paths.PA_MEDIA_DIR)
    src.mount('/pa/', '/pa_ex1')


    backup_log_file = backup_path + '/log.json'

    log = set(pajson.loadf(backup_log_file)[0] if os.path.isfile(backup_log_file) else [])

    for root, dirs, files in os.walk(mod_dir):
        for file in files:
            # skip files that aren't relavant
            if file.startswith('.') or file.endswith('modinfo.json'):
                continue


            path = _join(root.replace(mod_dir, ''), file).replace('\\', '/')

            mod_file = _join(root, file)
            pa_file = src.resolveFile(path)


            if pa_file == None:
                log.add(path)

                # copy file
                _copy(mod_file, _join(paths.PA_MEDIA_DIR, path))

            else:
                pa_path = pa_file.replace(paths.PA_MEDIA_DIR, '')

                bfile = _join(backup_path, pa_path)

                if not os.path.isfile(bfile):
                    # do backup
                    _copy(pa_file, bfile)

                # copy file
                _copy(mod_file, pa_file)


    with open(backup_log_file, 'w') as f:
        pajson.dump(list(log), f, indent=2)

def restore():
    backup_path = paths.PA_MEDIA_DIR + '/backup'
    backup_log_file = backup_path + '/log.json'
    log = pajson.loadf(backup_log_file)[0] if os.path.isfile(backup_log_file) else []

    fs = pafs(paths.PA_MEDIA_DIR)
    fs.mount('/pa/', '/pa_ex1')

    for root, dirs, files in os.walk(backup_path):
        for file in files:
            if file.endswith('log.json'):
                continue

            path = _join(root.replace(backup_path, ''), file).replace('\\', '/')

            src = _join(root, file)
            dst = _join(paths.PA_MEDIA_DIR, path)

            _copy(src, dst)

    for file in log:
        with contextlib.suppress(FileNotFoundError):
            os.remove(_join(paths.PA_MEDIA_DIR, file))

    # remove backup
    shutil.rmtree(backup_path)

