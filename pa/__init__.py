from os.path import isfile
from posixpath import join, normpath


def _join(path1, path2):
    if path1 is None or path2 is None:
        return None
    return join(path1, path2.strip("/"))


def _normalize(path):
    return path.replace('\\', '/')


class pafs:
    def __init__(self, rootPath):
        self.mounts = [('/', rootPath)]

    def mount(self, dest, path):
        self.mounts.insert(0, (dest, path))


    def unmount(self, dest):
        for mnt, path in self.mounts:
            if mnt == dest:
                self.mounts.remove((mnt, path))
                return

    def resolveFile(self, path):
        path = _normalize(path)
        for i in range(len(self.mounts)):
            mounts = self.mounts[i:]

            file_path = path
            for mount_point, mount_path in mounts:
                if file_path.startswith(mount_point):
                    file_path = _join(mount_path, file_path[len(mount_point):])
                # if we are mounting the root, we should not propogate further
                if mount_point == '/':
                    break

            if isfile(file_path):
                return normpath(file_path)

        return None

    # returns True if any of the roots has that file
    def hasFile(self, path):
        return self.resolveFile(path) != None