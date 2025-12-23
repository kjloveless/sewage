import os

import git as g
import objects as o

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
    ret += int(i.sha, 16)
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
