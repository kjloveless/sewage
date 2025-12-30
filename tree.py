import os

import git as g
import objects as o
import repo as r

def tree_parse_one(raw, start=0):
  # find the space terminator of the mode
  x = raw.find(b' ', start)
  assert x - start == 5 or x - start == 6

  # read the mode
  mode = raw[start:x]
  if len(mode) == 5:
    # normalize to six bytes
    mode = b'0' + mode

  # find the null terminator of the path
  y = raw.find(b'\x00', x)
  # and read the path
  path = raw[x + 1:y]

  # read the sha...
  raw_sha = int.from_bytes(raw[y+1:y+21], "big")
  # and convert it into a hex string, padded to 40 chars with zeros if needed
  sha = format(raw_sha, "040x")
  return y + 21, g.GitTreeLeaf(mode, path.decode("utf8"), sha)

#------------------------------------------------------------------------------
def tree_parse(raw):
  pos = 0
  max = len(raw)
  ret = list()
  while pos < max:
    pos, data = tree_parse_one(raw, pos)
    ret.append(data)

  return ret

#------------------------------------------------------------------------------
# notice this isn't a comparison function, but a conversion function. python's
# default sort doesn't accept a custom comparison function, like in most 
# languages, but a 'key' arguments that returns a new value, which is compared
# using the default rules. so we just return the leaf name, with an extra / if
# its a directory
def tree_leaf_sort_key(leaf):
  if leaf.mode.startswith(b"10"):
    return leaf.path
  else:
    return leaf.path + "/"

#------------------------------------------------------------------------------
def tree_serialize(obj):
  obj.items.sort(key=tree_leaf_sort_key)
  ret = b''
  for i in obj.items:
    ret += i.mode
    ret += b' '
    ret += i.path.encode("utf8")
    ret += b'\x00'
    sha = int(i.sha, 16)
    ret += sha.to_bytes(20, byteorder="big")
  return ret

#------------------------------------------------------------------------------
def tree_checkout(repo, tree, path):
  for item in tree.items:
    obj = o.object_read(repo, item.sha)
    dest = os.path.join(path, item.path)

    if obj.fmt == b'tree':
      os.mkdir(dest)
      tree_checkout(repo, obj, dest)
    elif obj.fmt == b'blob':
      # todo: support symlinks (identified by mode 12****)
      with open(dest, 'wb') as f:
        f.write(obj.blobdata)

#-------------------------------------------------------------------------------
def branch_get_active(repo):
  with open(r.repo_file(repo, "HEAD"), "r") as f:
    head = f.read()

  if head.startswith("ref: refs/heads/"):
    return head[16:-1]
  else:
    return False

#-------------------------------------------------------------------------------
def tree_to_dict(repo, ref, prefix=""):
  ret = dict()
  tree_sha = o.object_find(repo, ref, fmt=b"tree")
  tree = o.object_read(repo, tree_sha)

  for leaf in tree.items:
    full_path = os.path.join(prefix, leaf.path)

    # we read the object to extract its type (this is uselessly expensive;
    # we could just open it as a file and read the first few bytes)
    is_subtree = leaf.mode.startswith(b'04')

    # depending on the type, we either store the path (if it's a blob, so  a 
    # regular file), or recurse (if it's another tree. so a subdir)
    if is_subtree:
      ret.update(tree_to_dict(repo, leaf.sha, full_path))
    else:
      ret[full_path] = leaf.sha
  return ret
