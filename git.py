import os
import configparser

import repo as r
import kvlm as k
import tree as t

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
