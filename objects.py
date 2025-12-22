import os
import zlib
import hashlib

import repo as r
import git

def object_read(repo, sha):
  """read object sha from git repository repo. return a GitObject whose exact
type depends on the object"""

  path = r.repo_file(repo, "objects", sha[0:2], sha[2:])

  if not os.path.isfile(path):
    return None

  with open (path, "rb") as f:
    raw = zlib.decompress(f.read())

    # read object type
    x = raw.find(b' ')
    fmt = raw[0:x]

    # read and validate object size
    y = raw.find(b'\x00', x)
    size = int(raw[x:y].decode("ascii"))
    if size != len(raw) - y - 1:
      raise Exception(f"malformed object {sha}: bad length")

    # pick constructor
    match fmt:
      case b'commit'    : c=GitCommit
      case b'tree'      : c=GitTree
      case b'tag'       : c=GitTag
      case b'blob'      : c=git.GitBlob
      case _:
        raise Exception(f"unknown type {fmt.decode("ascii")} for object {sha}")

    # call constructor and return object
    return c(raw[y + 1:])

#------------------------------------------------------------------------------
def object_write(obj, repo=None):
  # serialize object data
  data = obj.serialize()
  # add header
  result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
  # compute hash
  sha = hashlib.sha1(result).hexdigest()

  if repo:
    # compute path
    path = repo.repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

    if not os.path.exists(path):
      with open(path, 'wb') as f:
        # compress and write
        f.write(zlib.compress(result))

  return sha

#------------------------------------------------------------------------------
def object_find(repo, name, fmt=None, follow=True):
  return name

#------------------------------------------------------------------------------
def object_hash(fd, fmt, repo=None):
  """hash object, writing it to repo if provided"""
  data = fd.read()

  # choose constructor according to fmt argument
  match fmt:
    case b'commit'      : obj=git.GitCommit(data)
    case b'tree'        : obj=git.GitTree(data)
    case b'tag'         : obj=git.GitTag(data)
    case b'blob'        : obj=git.GitBlob(data)
    case _: raise Exception(f"unknown type {fmt}")

  return object_write(obj, repo)
