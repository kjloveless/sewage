import argparse
import sys
import os

import repo as r 
import objects as o
import tree as t
import ref

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
  show_ref(repo, refs, prefix="refs")

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

def show_ref(repo, refs, with_hash=True, prefix=""):
  if prefix:
    prefix = prefix + '/'
  for k, v in refs.items():
    if type(v) == str and with_hash:
      print(f"{v} {prefix}{k}")
    elif type(v) == str:
      print(f"{prefix}{k}")
    else:
      show_ref(repo, v, with_hash=with_hash, prefix=f"{prefix}{k}")
