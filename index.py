import os
from math import ceil

import repo as r
import git

def index_read(repo):
  index_file = r.repo_file(repo, "index")

  # new repositories have no index
  if not os.path.exists(index_file):
    return git.GitIndex()

  with open(index_file, 'rb') as f:
    raw = f.read()

  header = raw[:12]
  signature = header[:4]
  assert signature == b"DIRC" # stands for DirCache
  version = int.from_bytes(header[4:8], "big")
  assert version == 2, "sewage only supports index file version 2"
  count = int.from_bytes(header[8:12], "big")

  entries = list()

  content = raw[12:]
  idx = 0
  for i in range(0, count):
    # read creation time, as a unix timestamp (seconds since
    # 1970-01-01 00:00:00, the "epoch")
    ctime_s = int.from_bytes(content[idx: idx+4], "big")
    # read creation time, as nanoseconds after that timestamps,
    # for extra precision
    ctime_ns = int.from_bytes(content[idx+4:idx+8], "big")
    # same for modification time: first seconds from epoch
    mtime_s = int.from_bytes(content[idx+8:idx+12], "big")
    # the extra nanoseconds
    mtime_ns = int.from_bytes(content[idx+12:idx+16], "big")
    # device id
    dev = int.from_bytes(content[idx+16:idx+20], "big")
    # inode
    ino = int.from_bytes(content[idx+20:idx+24], "big")
    # ignored
    unused = int.from_bytes(content[idx+24:idx+26], "big")
    assert 0 == unused
    mode = int.from_bytes(content[idx+26:idx+28], "big")
    mode_type = mode >> 12
    assert mode_type in [0b1000, 0b1010, 0b1110]
    mode_perms = mode & 0b0000000111111111
    # user id
    uid = int.from_bytes(content[idx+28:idx+32], "big")
    # group id
    gid = int.from_bytes(content[idx+32:idx+36], "big")
    # size
    fsize = int.from_bytes(content[idx+36:idx+40], "big")
    # sha (object id). we'll store it as a lowercase hex string for consistency
    sha = format(int.from_bytes(content[idx+40:idx+60], "big"), "040x")
    # flags we're going to ignore
    flags = int.from_bytes(content[idx+60:idx+62], "big")
    # parse flags
    flag_assume_valid = (flags & 0b1000000000000000) != 0
    flag_extended = (flags & 0b0100000000000000) != 0
    assert not flag_extended
    flag_stage = flags & 0b0011000000000000
    # length of the name, this is stored on 12 bites, some max value is 0xFFF,
    # 4095. since names occasionally go beyond that length, git treats 0xFFF
    # as meaning at least 0xFFF, and looks for the final 0x00 to find the end 
    # of the name --- at a small, and probably very rare performance cost
    name_length = flags & 0b0000111111111111

    # we've read 62 bytes so far
    idx += 62

    if name_length < 0xFFF:
      assert content[idx + name_length] == 0x00
      raw_name = content[idx:idx+name_length]
      idx += name_length + 1
    else:
      print(f"notice: name id 0x{name_length:X} bytes long")
      # this probably wasn't tested enough. it works with a path of exactly 
      # 0xFFF bytes. any extra bytes broke something between git, the shell, 
      # and filesystem
      null_idx = content.find(b'\x00', idx + 0xFFF)
      raw_name = content[idx:null_idx]
      idx = null_idx + 1

    # just parse the name as utf8
    name = raw_name.decode("utf8")

    # data is padded on multiples of eight bytes for pointer alignment, so we
    # skip as many bytes as we need for the next read to start at the right
    # position
    
    idx = 8 * ceil(idx / 8)

    # and we add this entry to our list
    entries.append(git.GitIndexEntry(ctime=(ctime_s, ctime_ns),
                                     mtime=(mtime_s, mtime_ns),
                                     dev=dev,
                                     ino=ino,
                                     mode_type=mode_type,
                                     mode_perms=mode_perms,
                                     uid=uid,
                                     gid=gid,
                                     fsize=fsize,
                                     sha=sha,
                                     flag_assume_valid=flag_assume_valid,
                                     flag_stage=flag_stage,
                                     name=name))

  return git.GitIndex(version=version, entries=entries)
