import argparse
import sys

import repo as r 
import objects as o

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
