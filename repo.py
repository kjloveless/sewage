import os
import configparser

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
    cf = repo_file(self, "config")

    if cf and os.path.exists(cf):
      self.conf.read([cf])
    elif not force:
      raise Exception("configuration file missing")

    if not force:
      vers = int(self.conf.get("core", "repositoryformatversion"))
      if vers != 0:
        raise Exception(f"unsupported repositoryformatversion: {vers}")

###----------------------------------------------------------------------------

def repo_path(repo, *path):
  """compute path under repo's gitdir"""
  return os.path.join(repo.gitdir, *path)

def repo_file(repo, *path, mkdir=False):
  """same as repo_path, but create dirname(*path) if absent. for example, 
repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\" will create
.git/refs/remotes/origin"""

  if repo_dir(repo, *path[:-1], mkdir=mkdir):
    return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
  """same as repo_path, but mkdir *path if mkdir is absent"""

  path = repo_path(repo, *path)

  if os.path.exists(path):
    if (os.path.isdir(path)):
      return path
    else:
      raise Exception(f"not a directory {path}")

  if mkdir:
    os.makedirs(path)
    return path
  else:
    return None

def repo_default_config():
  ret = configparser.ConfigParser()

  ret.add_section("core")
  ret.set("core", "repositoryformatversion", "0")
  ret.set("core", "filemode", "false")
  ret.set("core", "bare", "false")

  return ret

def repo_create(path):
  """create a new repository at path"""

  repo = GitRepository(path, True)

  # first, we make sure the path either doesn't exist or is an empty dir
  if os.path.exists(repo.worktree):
    if not os.path.isdir(repo.worktree):
      raise Exception(f"{path} is not a directory")
    if os.path.exists(repo.gitdir) and os.lsitdir(repo.gitdir):
      raise Exception(f"{path} is not empty!")
  else:
    os.makedirs(repo.worktree)

  assert repo_dir(repo, "branches", mkdir=True)
  assert repo_dir(repo, "objects", mkdir=True)
  assert repo_dir(repo, "refs", "tags", mkdir=True)
  assert repo_dir(repo, "refs", "heads", mkdir=True)

  # .git/description
  with open(repo_file(repo, "description"), "w") as f:
    f.write("unnamed repository; edit this file 'descriptiion' to name the repository\n")

  # .git/HEAD
  with open(repo_file(repo, "HEAD"), "w") as f:
    f.write("ref: refs/heads/main\n")

  with open(repo_file(repo, "config"), "w") as f:
    config = repo_default_config()
    config.write(f)

  return repo
