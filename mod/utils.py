import os
import shutil
import contextlib

from pa_tools.pa import pafs
from pa_tools.pa import paths
from pa_tools.pa import pajson


def create_pafs(is_titans=True, mount_backup=True):
    backup_path = _join(paths.PA_MEDIA_DIR, 'backup')

    mount_backup = mount_backup and os.path.exists(backup_path)

    src = pafs(paths.PA_MEDIA_DIR)
    if mount_backup:
        src.mount('/pa/', _join(backup_path, 'pa'))

    if is_titans:
        src.mount('/pa/', '/pa_ex1')
        if mount_backup:
            src.mount('/pa/', _join(backup_path, '/pa_ex1'))

    return src


def _join(path1, path2):
    if path1 is None or path2 is None:
        return None
    return os.path.join(path1, path2.strip("/"))

def _copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)

def deploy_debug(mod_dir, is_titans):
    print('======== DEBUG_DEPLOY')
    backup_path = paths.PA_MEDIA_DIR + '/backup'
    print('Creating backup directory', backup_path)
    os.makedirs(backup_path, exist_ok=True)

    src = create_pafs(is_titans, False)

    backup_log_file = backup_path + '/log.json'

    log = set(pajson.loadf(backup_log_file)[0] if os.path.isfile(backup_log_file) else [])

    create_list = []
    replace_list = []

    for root, dirs, files in os.walk(mod_dir):
        for file in files:
            # skip files that aren't relavant
            if file.startswith('.') or file.endswith('modinfo.json'):
                continue


            path = _join(root.replace(mod_dir, ''), file).replace('\\', '/')

            mod_file = _join(root, file)
            pa_file = src.resolveFile(path)


            if pa_file == None or path in log:
                create_list.append((mod_file, path))
            else:
                replace_list.append((mod_file, pa_file))

    for mod_file,path in create_list:
        if is_titans and path.startswith('/pa/'):
            path = '/pa_ex1/' + path[len('/pa/'):]

        print ('creating file:', path)
        log.add(path)

        # copy file
        _copy(mod_file, _join(paths.PA_MEDIA_DIR, path))

    for mod_file,pa_file in replace_list:
        print ('copy:', mod_file, pa_file)
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
    print('======== Restore')
    backup_path = paths.PA_MEDIA_DIR + '/backup'
    backup_log_file = backup_path + '/log.json'
    log = pajson.loadf(backup_log_file)[0] if os.path.isfile(backup_log_file) else []

    fs = pafs(paths.PA_MEDIA_DIR)
    fs.mount('/pa/', '/pa_ex1')

    for file in log:
        with contextlib.suppress(FileNotFoundError):
            to_remove = _join(paths.PA_MEDIA_DIR, file);
            print('removed:', to_remove)
            os.remove(to_remove)


    for root, dirs, files in os.walk(backup_path):
        for file in files:
            if file.endswith('log.json'):
                continue

            path = _join(root.replace(backup_path, ''), file).replace('\\', '/')

            src = _join(root, file)
            dst = _join(paths.PA_MEDIA_DIR, path)

            _copy(src, dst)

            print('restoring:', dst)

    # remove backup
    shutil.rmtree(backup_path, ignore_errors=True)

