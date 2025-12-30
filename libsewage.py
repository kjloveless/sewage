import argparse
import sys
import os
from datetime import datetime
import grp, pwd

import repo as r 
import objects as o
import tree as t
import ref as ref
import index as i
import git

argparser = argparse.ArgumentParser(description="the worst content tracker")

argsubparsers = argparser.add_subparsers(title="commands", dest="command")
argsubparsers.required = True


argsp = argsubparsers.add_parser("init", help="initialize a new, empty repository")
argsp.add_argument("path",
                   metavar="directory",
                   nargs="?",
                   default=".",
                   help="where to create the repository")

argsp = argsubparsers.add_parser("cat-file",
                                 help="provide content of repository objects")
argsp.add_argument("type",
                   metavar="type",
                   choices=["blob", "commit", "tag", "tree"],
                   help="specify the type")
argsp.add_argument("object",
                   metavar="object",
                   help="the object to display")

argsp = argsubparsers.add_parser(
    "hash-object",
    help="compute object ID and optionally creates a blob from a file")
argsp.add_argument("-t",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default="blob",
                   help="specify the type")
argsp.add_argument("-w",
                   dest="write",
                   action="store_true",
                   help="actually write the object into the database")
argsp.add_argument("path",
                   help="read object from <file>")

argsp = argsubparsers.add_parser("log", help="display history of a given commit")
argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="commit to start at")

argsp = argsubparsers.add_parser("ls-tree", help="pretty-print a tree object")
argsp.add_argument("-r",
                   dest="recursive",
                   action="store_true",
                   help="recurse into sub-trees")
argsp.add_argument("tree",
                   help="a tree-ish object")

argsp = argsubparsers.add_parser("checkout", help="checkout a commit inside a directory")
argsp.add_argument("commit",
                   help="the commit or tree to checkout")
argsp.add_argument("path",
                   help="the empty directory to checkout on")

argsp = argsubparsers.add_parser("show-ref", help="list references")

argsp = argsubparsers.add_parser("tag", help="list and create tags")
argsp.add_argument("-a",
                   action="store_true",
                   dest="create_tag_object",
                   help="whether to create a tag object")
argsp.add_argument("name",
                   nargs="?",
                   help="the new tag's name")

argsp.add_argument("object",
                   default="HEAD",
                   nargs="?",
                   help="the object the new tag will point to")

argsp = argsubparsers.add_parser("rev-parse",
                                 help="parse revision (or other objects) identifiers")
argsp.add_argument("--sewage-type",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default=None,
                   help="specify the expected type")
argsp.add_argument("name", help="the name to parse")

argsp = argsubparsers.add_parser("ls-files", help="list all the stage files")
argsp.add_argument("--verbose", action="store_true", help="show everything")

argsp = argsubparsers.add_parser("check-ignore", help="check path(s) against ignore rules.")
argsp.add_argument("path", nargs="+", help="paths to check")

argsp = argsubparsers.add_parser("status", help="show the working tree status.")

def main(argv=sys.argv[1:]):
  args = argparser.parse_args(argv)
  match args.command:
    case "add"            : cmd_add(args)
    case "cat-file"       : cmd_cat_file(args)
    case "check-ignore"   : cmd_check_ignore(args)
    case "checkout"       : cmd_checkout(args)
    case "commit"         : cmd_commit(args)
    case "hash-object"    : cmd_hash_object(args)
    case "init"           : cmd_init(args)
    case "log"            : cmd_log(args)
    case "ls-files"       : cmd_ls_files(args)
    case "ls-tree"        : cmd_ls_tree(args)
    case "rev-parse"      : cmd_rev_parse(args)
    case "rm"             : cmd_rm(args)
    case "show-ref"       : cmd_show_ref(args)
    case "status"         : cmd_status(args)
    case "tag"            : cmd_tag(args)
    case _                : print("unknown command")

def cmd_status(_):
  repo = r.repo_find()
  index = i.index_read(repo)

  cmd_status_branch(repo)
  cmd_status_head_index(repo, index)
  print()
  cmd_status_index_worktree(repo, index)

def cmd_status_head_index(repo, index):
  print("changes to be committed:")

  head = t.tree_to_dict(repo, "HEAD")
  for entry in index.entries:
    if entry.name in head:
      if head[entry.name] != entry.sha:
        print(" modified:", entry.name)
      del head[entry.name] # delete the key
    else:
      print(" added:    ", entry.name)

  # keys still in HEAD are files that we haven't met in the index and thus
  # have been deleted
  for entry in head.keys():
    print(" deleted: ", entry)

def cmd_status_index_worktree(repo, index):
  print("changes not staged for commit:")

  ignore = git.gitignore_read(repo)

  gitdir_prefix = repo.gitdir + os.path.sep

  all_files = list()

  # we begin by walking the filesystem
  for (root, _, files) in os.walk(repo.worktree, True):
    if root == repo.gitdir or root.startswith(gitdir_prefix):
      continue
    for f in files:
      full_path = os.path.join(root, f)
      rel_path = os.path.relpath(full_path, repo.worktree)
      all_files.append(rel_path)

  # we now traverse the index, and compare real files with the cached 
  # versions
  for entry in index.entries:
    full_path = os.path.join(repo.worktree, entry.name)

    # that file *name* is in the index
    if not os.path.exists(full_path):
      print(" deleted: ", entry.name)
    else:
      stat = os.stat(full_path)
      
      # compare metadata
      ctime_ns = entry.ctime[0] * 10**9 + entry.ctime[1]
      mtime_ns = entry.mtime[0] * 10**9 + entry.mtime[1]
      if (stat.st_ctime_ns != ctime_ns) or (stat.st_mtime_ns != mtime_ns):
        # if different, deep compare. @TODO: "this will crash on symlinks to
        # dir
        with open(full_path, "rb") as fd:
          new_sha = o.object_hash(fd, b"blob", None)
          # if the hashes are the same, the files are actuallythe same
          same = entry.sha == new_sha

          if not same:
            print(" modified:", entry.name)

    if entry.name in all_files:
      all_files.remove(entry.name)

  print()
  print("untracked files:")

  for f in all_files:
    # @TODO: if a fulldirectory is untracked, we should display its name
    # without its contents
    if not git.check_ignore(ignore, f):
      print(" ", f)

def cmd_status_branch(repo):
  branch = t.branch_get_active(repo)
  if branch:
    print(f"on branch {branch}")
  else:
    print(f"HEAD detached at {o.object_find(repo, 'HEAD')}")

def cmd_check_ignore(args):
  repo = r.repo_find()
  rules = git.gitignore_read(repo)
  for path in args.path:
    if git.check_ignore(rules, path):
      print(path)

def cmd_ls_files(args):
  repo = r.repo_find()
  index = i.index_read(repo)
  if args.verbose:
    print(f"index file format v{index.version}, containing {len(index.entries)} entries")

  for e in index.entries:
    print(e.name)
    if args.verbose:
      entry_type = { 0b1000: "regular file",
                      0b1010: "symlink",
                      0b1110: "git link" }[e.mode_type]
      print(f"  {entry_type} with perms: {e.mode_perms:o}")
      print(f"  on blob: {e.sha}")
      print(f"  created: {datetime.fromtimestamp(e.ctime[0])}.{e.ctime[1]}, modified: {datetime.fromtimestamp(e.mtime[0])}.{e.mtime[1]}")
      print(f"  device: {e.dev}, inode: {e.ino}")
      print(f"  user: {pwd.getpwuid(e.uid).pw_name} ({e.uid}) group: {grp.getgrgid(e.gid).gr_name} ({e.gid})")
      print(f"  flags: stage={e.flag_stage} assume_valid={e.flag_assume_valid}")

def cmd_init(args):
  r.repo_create(args.path)

def cmd_cat_file(args):
  repo = r.repo_find()
  cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
  obj = o.object_read(repo, o.object_find(repo, obj, fmt=fmt))
  sys.stdout.buffer.write(obj.serialize())

def cmd_hash_object(args):
  if args.write:
    repo = r.repo_find()
  else:
    repo = None

  with open(args.path, "rb") as fd:
    sha = o.object_hash(fd, args.type.encode(), repo)
    print(sha)

def cmd_ls_tree(args):
  repo = r.repo_find()
  ls_tree(repo, args.tree, args.recursive)

def cmd_log(args):
  repo = r.repo_find()

  print("digraph sewage{")
  print(" node[shape=rect]")
  log_graphviz(repo, o.object_find(repo, args.commit), set())
  print("}")

def cmd_checkout(args):
  repo = r.repo_find()

  obj = o.object_read(repo, o.object_find(repo, args.commit))

  # if the object is a commit, we grab its tree
  if obj.fmt == b'commit':
    obj = o.object_read(repo, obj.kvlm[b'tree'].decode("ascii"))

  # verify that path is an empty directory
  if os.path.exists(args.path):
    if not os.path.isdir(args.path):
      raise Exception(f"not a directory {args.path}")
    if os.listdir(args.path):
      raise Exception(f"not empty {args.path}")
  else:
    os.makedirs(args.path)

  t.tree_checkout(repo, obj, os.path.realpath(args.path))

def cmd_show_ref(args):
  repo = r.repo_find()
  refs = ref.ref_list(repo)
  ref.show_ref(repo, refs, prefix="refs")

def cmd_tag(args):
  repo = r.repo_find()

  if args.name:
    tag_create(repo,
               args.name,
               args.object,
               create_tag_object = args.create_tag_object)
  else:
    refs = ref.ref_list(repo)
    ref.show_ref(repo, refs["tags"], with_hash=False)

def cmd_rev_parse(args):
  if args.type:
    fmt = args.type.encode()
  else:
    fmt = None

  repo = r.repo_find()

  print(o.object_find(repo, args.name, fmt, follow=True))

def log_graphviz(repo, sha, seen):
  if sha in seen:
    return
  seen.add(sha)

  commit = o.object_read(repo, sha)
  message = commit.kvlm[None].decode("utf8").strip()
  message = message.replace("\\", "\\\\")
  message = message.replace("\"", "\\\"")

  if "\n" in message: # keep only the first line
    message = message[:message_index("\n")]

  print(f"  c_{sha} [label=\"{sha[0:7]}:  {message}\"]")
  assert commit.fmt == b'commit'

  if not b'parent' in commit.kvlm.keys():
    # base case: the initial commit
    return

  parents = commit.kvlm[b'parent']

  if type(parents) != list:
    parents = [ parents ]

  for p in parents:
    p = p.decode("ascii")
    print(f"  c_{sha} -> c_{p};")
    log_graphviz(repo, p, seen)

def ls_tree(repo, ref, recursive=None, prefix=""):
  sha = o.object_find(repo, ref, fmt=b"tree")
  obj = o.object_read(repo, sha)
  for item in obj.items:
    if len(item.mode) == 5:
      type = item.mode[0:1]
    else:
      type = item.mode[0:2]

    match type:
      case b'04': type = "tree"
      case b'10': type = "blob"
      case b'12': type = "blob"
      case b'16': type = "commit"
      case _: raise Exception(f"weird tree lead mode {item.mode}")

    if not (recursive and type=='tree'):
      print(f"{'0' * (6 - len(item.mode)) + item.mode.decode("ascii")} {type} {item.sha}\t{os.path.join(prefix, item.path)}")
    else:
      ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))

def tag_create(repo, name, reference, create_tag_object=False):
  # get the GitObject from the object reference
  sha = o.object_find(repo, reference)

  if create_tag_object:
    # create tag object (commit)
    tag = git.GitTag()
    tag.kvlm = dict()
    tag.kvlm[b'object'] = sha.encode()
    tag.kvlm[b'type'] = b'commit'
    tag.kvlm[b'tag'] = name.encode()
    # feel free to let the user give their name
    # notice you can fix this after commit
    tag.kvlm[b'tagger'] = b'sewage <sewage@example.com>'
    # and a tag message
    tag.kvlm[None] = b"a tag generated by sewage, which won't let you customize this message\n"
    tag_sha = o.object_write(tag, repo)
    # create a reference
    ref.ref_create(repo, "tags/" + name, tag_sha)
  else:
    # create lightweight tag (ref)
    ref.ref_create(repo, "tags/" + name, sha)

