import os

import repo as r

def ref_resolve(repo, ref):
  path = r.repo_file(repo, ref)

  # sometimes, an indirect reference may be broken. this is normal in one 
  # specific case: we're looking for HEAD on a new repository with no commits.
  # in that case, .git/HEAD points to "ref:refs/heads/main", but 
  # .git/refs/heads/main doesn't exist yet (since there's no commit for it to
  # refer to)
  if not os.path.isfile(path):
    return None

  with open(path, 'r') as fp:
    data = fp.read()[:-1]
    # drop final \n ^^^^^
  if data.startswith("ref: "):
    return ref_resolve(repo, data[5:])
  else:
    return data

#------------------------------------------------------------------------------
def ref_list(repo, path=None):
  if not path:
    path = r.repo_dir(repo, "refs")
  ret = dict()
  # git shows refs sorted. to do the same, we sort the output of listdir
  for f in sorted(os.listdir(path)):
    can = os.path.join(path, f)
    if os.path.isdir(can):
      ret[f] = ref_list(repo, can)
    else:
      ret[f] = ref_resolve(repo, can)

  return ret
