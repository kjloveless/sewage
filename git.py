import os
import configparser
from fnmatch import fnmatch

import repo as r
import kvlm as k
import tree as t
import index as i
import objects as o

class GitObject(object):
  def __init__(self, data=None):
    if data != None:
      self.deserialize(data)
    else:
      self.init()

  def serialize(self, repo):
    """this function MUST be implemented by subclasses.

it must read the object's contents from self.data, a byte string, and do
whatever it takes to convert it into a meaningful representation. what 
exactly that meands depends on each subclass."""
    raise Exception("unimplemented")

  def deserialize(self, data):
    raise Exception("unimplemented")

  def init(self):
    pass # just do nothing

###############################################################################

class GitBlob(GitObject):
  fmt = b'blob'

  def serialize(self):
    return self.blobdata

  def deserialize(self, data):
    self.blobdata = data

###############################################################################
class GitRepository(object):
  """a git repository"""

  worktree = None
  gitdir = None
  conf = None

  def __init__(self, path, force=False):
    self.worktree = path
    self.gitdir = os.path.join(path, ".git")

    if not (force or os.path.isdir(self.gitdir)):
      raise Exception(f"not a git repository: {path}")

    
    # read configuration file in .git/config
    self.conf = configparser.ConfigParser()
    cf = r.repo_file(self, "config")

    if cf and os.path.exists(cf):
      self.conf.read([cf])
    elif not force:
      raise Exception("configuration file missing")

    if not force:
      vers = int(self.conf.get("core", "repositoryformatversion"))
      if vers != 0:
        raise Exception(f"unsupported repositoryformatversion: {vers}")

###############################################################################
class GitCommit(GitObject):
  fmt = b'commit'

  def deserialize(self, data):
    self.kvlm = k.kvlm_parse(data)

  def serialize(self):
    return k.kvlm_serialize(self.kvlm)

  def init(self):
    self.kvlm = dict()

###############################################################################
class GitTreeLeaf(object):
  def __init__(self, mode, path, sha):
    self.mode = mode
    self.path = path
    self.sha = sha

###############################################################################
class GitTree(GitObject):
  fmt = b'tree'

  def deserialize(self, data):
    self.items = t.tree_parse(data)

  def serialize(self):
    return t.tree_serialize(self)

  def init(self):
    self.items = list()

###############################################################################
class GitTag(GitCommit):
  fmt = b'tag'

###############################################################################
class GitIndexEntry(object):
  def __init__(self, ctime=None, mtime=None, dev=None, ino=None,
               mode_type=None, mode_perms=None, uid=None, gid=None,
               fsize=None, sha=None, flag_assume_valid=None,
               flag_stage=None, name=None):
    # the last time a files metadata changed. this is a pair 
    # (timestamp in seconds, nanoseconds)
    self.ctime = ctime
    # the last time a files data changed. this is a pair 
    # (timestamp in seconds, nanoseconds)
    self.mtime = mtime
    # the id of device containing this file
    self.dev = dev
    # the files inode number
    self.ino = ino
    # the object type, either b1000 (regular), b1010 (symlink), b1110(gitlink)
    self.mode_type = mode_type
    # the objects permissions, an integer
    self.mode_perms = mode_perms
    # user id of owner
    self.uid = uid
    # group id of owner
    self.gid = gid
    # size of this object, in bytes
    self.fsize = fsize
    # the objects sha
    self.sha = sha
    self.flag_assume_valid = flag_assume_valid
    self.flag_stage = flag_stage
    # name of the object (full path this time)
    self.name = name

###############################################################################
class GitIndex(object):
  version = None
  entries = []
  # ext = None
  # sha = None

  def __init__(self, version=2, entries=None):
    if not entries:
      entries = list()

    self.version = version
    self.entries = entries

################################################################################
class GitIgnore(object):
    absolute = None
    scoped = None

    def __init__(self, absolute, scoped):
        self.absolute = absolute
        self.scoped = scoped

#-------------------------------------------------------------------------------
def gitignore_read(repo):
    ret = GitIgnore(absolute=list(), scoped=dict())

    # read local configuration in .git/info/exclude
    repo_file = os.path.join(repo.gitdir, "info/exclude")
    if os.path.exists(repo_file):
        with open(repo_file, "r") as f:
            ret.absolute.append(gitignore_parse(f.readlines()))

    # global configuration
    if "XDG_CONFIG_HOME" in os.environ:
        config_home = os.environ["XDG_CONFIG_HOME"]
    else:
        config_home = os.path.expanduser("~/.config")
    global_file = os.path.join(config_home, ".git/ignore")

    if os.path.exists(global_file):
        with open(global_file, "r") as f:
            ret.absolute.append(gitignore_parse(f.readlines()))

    # .gitignore files in the index
    index = i.index_read(repo)

    for entry in index.entries:
      if entry.name == ".gitignore" or entry.name.endswith("/.gitignore"):
        dir_name = os.path.dirname(entry.name)
        contents = o.object_read(repo, entry.sha)
        lines = contents.blobdata.decode("utf8").splitlines()
        ret.scoped[dir_name] = gitignore_parse(lines)
    return ret

#-------------------------------------------------------------------------------
def gitignore_parse1(raw):
    raw = raw.strip() # remove leadeing/trailing spaces

    if not raw or raw[0] == "#":
        return None
    elif raw[0] == "!":
        return (raw[1:], False)
    elif raw[0] == "\\":
        return (raw[1:], True)
    else:
        return (raw, True)

#-------------------------------------------------------------------------------
def gitignore_parse(lines):
    ret = list()

    for line in lines:
        parsed = gitignore_parse1(line)
        if parsed:
            ret.append(parsed)

    return ret

#-------------------------------------------------------------------------------
def check_ignore1(rules, path):
    result = None
    for (pattern, value) in rules:
        if fnmatch(path, pattern):
            result = value
    return result

#-------------------------------------------------------------------------------
def check_ignore_scoped(rules, path):
    parent = os.path.dirname(path)
    while True:
        if parent in rules:
            result = check_ignore1(rules[parent], path)
            if result != None:
                return result
        if parent == "":
            break
        parent = os.path.dirname(parent)
    return None

#-------------------------------------------------------------------------------
def check_ignore_absolute(rules, path):
    parent = os.path.dirname(path)
    for ruleset in rules:
        result = check_ignore1(ruleset, path)
        if result != None:
            return result
    return False # reasonable default

#-------------------------------------------------------------------------------
def check_ignore(rules, path):
    if os.path.isabs(path):
        raise Exception("this function requires path to be relative to the repository's root")

    result = check_ignore_scoped(rules.scoped, path)
    if result != None:
        return result

    return check_ignore_absolute(rules.absolute, path)
