import os
import zlib
import hashlib
import re

import repo as r
import git
import ref

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
      case b'commit'    : c=git.GitCommit
      case b'tree'      : c=git.GitTree
      case b'tag'       : c=git.GitTag
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
    path = r.repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

    if not os.path.exists(path):
      with open(path, 'wb') as f:
        # compress and write
        f.write(zlib.compress(result))

  return sha

#------------------------------------------------------------------------------
def object_find(repo, name, fmt=None, follow=True):
  sha = object_resolve(repo, name)

  if not sha:
    raise Exception(f"no such referemce {name}")

  if len(sha) > 1:
    raise Exception(f"ambiguous reference {name}: candidates are:\n - {'\n - '.join(sha)}")

  sha = sha[0]

  if not fmt:
    return sha

  while True:
    obj = object_read(repo, sha)
    #     ^^^^^^^^^^^^^ < this is a bit aggressive: we're reading the full
    #     object just to get its type. and we're doing that in a loop, albeit
    #     normally short. don't expect high performance here
    if obj.fmt == fmt:
      return sha

    if not follow:
      return None

    # follow tags
    if obj.fmt == b'tag':
      sha = obj.kvlm[b'object'].decode("ascii")
    elif obj.fmt == b'commit' and fmt == b'tree':
      sha = obj.kvlm[b'tree'].decode("ascii")
    else:
      return None



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

#------------------------------------------------------------------------------
def object_resolve(repo, name):
  """resolve name to an object hash in repo.

this function is aware of:

  - the HEAD literal
  - short and long hashes
  - tags
  - branches
  - remote branches"""
  candidates = list()
  hashRE = re.compile(r"^[0-9A-Fa-f]{4,40}$")

  # empty string? abort
  if not name.strip():
    return None

  # head is ambiguous
  if name == "HEAD":
    return [ ref.ref_resolve(repo, "HEAD") ]

  # if it's a hex string, try for a hash
  if hashRE.match(name):
    # this may be a hash, either small or full. 4 seems to be the minimal 
    # length for git to consider something a short hash. this limit is 
    # documented in man git-rev-parse
    name = name.lower()
    prefix = name[0:2]
    path = r.repo_dir(repo, "objects", prefix, mkdir=False)
    if path:
      rem = name[2:]
      for f in os.listdir(path):
        if f.startswith(rem):
          # notice a string startswith() itself, so this works for full hashes
          candidates.append(prefix + f)

  # try for referencees
  as_tag = ref.ref_resolve(repo, "refs/tags/" + name)
  if as_tag:
    candidates.append(as_tag)

  as_branch = ref.ref_resolve(repo, "refs/heads/" + name)
  if as_branch:
    candidates.append(as_branch)

  as_remote_branch = ref.ref_resolve(repo, "refs/remotes/" + name)
  if as_remote_branch:
    candidates.append(as_remote_branch)

  return candidates
