from __future__ import division

'''
Author      : Lyubimov, A.Y.
Created     : 10/12/2014
Last Changed: 06/19/2015
Description : Module with miscellaneous useful functions and classes
'''

import os
import sys
from cStringIO import StringIO

from datetime import datetime
iota_version = '1.0.007'
now = "{:%A, %b %d, %Y. %I:%M %p}".format(datetime.now())

# For GUI
gui_description = '''The integration optimization, triage and
analysis (IOTA) toolkit for the processing of serial diffraction data.

Reference: Lyubimov, et al., J Appl Cryst, 2016
'''

prime_description = ''' The Post-RefInement and MErging (PRIME) program for
the scaling, merging and post-refinement of integrated diffraction images.

Reference: Uervirojnangkoorn, et al., eLife, 2015'''

gui_license = ''' IOTA is distributed under open source license '''
prime_license = ''' PRIME is distributed under open source license'''
cxi_merge_license = ''' cxi.merge is distributed under open source license '''


class Capturing(list):
  """ Class used to capture stdout from cctbx.xfel objects. Saves output in
  appendable list for potential logging.
  """

  def __enter__(self):
    self._stdout = sys.stdout
    self._stderr = sys.stderr
    sys.stdout = self._stringio_stdout = StringIO()
    sys.stderr = self._stringio_stderr = StringIO()
    return self
  def __exit__(self, *args):
    self.extend(self._stringio_stdout.getvalue().splitlines())
    sys.stdout = self._stdout
    self.extend(self._stringio_stderr.getvalue().splitlines())
    sys.stderr = self._stderr


def get_mpi_rank_and_size():
  from mpi4py import MPI
  comm = MPI.COMM_WORLD
  rank = comm.Get_rank() # each process in MPI has a unique id, 0-indexed
  size = comm.Get_size() # size: number of processes running in this job
  return rank, size

def main_log(logfile, entry, print_tag=False):
  """ Write main log (so that I don't have to repeat this every time). All this
      is necessary so that I don't have to use the Python logger module, which
      creates a lot of annoying crosstalk with other cctbx.xfel modules.
  """
  if logfile != None:
    with open(logfile, 'a') as lf:
      lf.write('{}\n'.format(entry))

  if print_tag:
    print entry

def set_base_dir(dirname=None, sel_flag=False, out_dir=None):
  """ Generates a base folder for converted pickles and/or grid search and/or
      integration results; creates subfolder numbered one more than existing
  """
  def check_dirname(path, subdirname):
    if os.path.isdir(os.path.join(path, subdirname)):
      try:
        int(subdirname)
        return True
      except ValueError:
        return False
    else:
      return False

  if out_dir == None and dirname != None:
    path = os.path.abspath(os.path.join(os.curdir, dirname))
  elif out_dir != None and dirname == None:
    path = os.path.abspath(out_dir)
  elif out_dir == None and dirname == None:
    path = os.path.abspath(os.curdir)
  else:
    path = os.path.join(os.path.abspath(out_dir), dirname)
  if os.path.isdir(path):
    num_dirs = len([dir for dir in os.listdir(path) if check_dirname(path, dir)])
    if sel_flag:
      new_path = "{}/{:03d}".format(path, num_dirs)
    else:
      new_path = "{}/{:03d}".format(path, num_dirs + 1)
  else:
    new_path = "{}/001".format(path)
  return new_path

def find_base_dir(dirname):
  """ Function to determine the current folder name """
  def check_dirname(path, subdirname):
    if os.path.isdir(os.path.join(path, subdirname)):
      try:
        int(subdirname)
        return True
      except ValueError:
        return False
    else:
      return False

  path = os.path.abspath(os.path.join(os.curdir, dirname))
  if os.path.isdir(path):
    if len(os.listdir(path)) > 0:
      dirs = [int(i) for i in os.listdir(path) if check_dirname(path, i)]
      found_path = "{}/{:03d}".format(path, max(dirs))
    else:
      found_path = path
  else:
    found_path = os.curdir
  return found_path


def make_image_path(raw_img, input_base, base_path):
  """ Makes path for output images """
  path = os.path.dirname(raw_img)
  if os.path.relpath(path, input_base) == '.':
    dest_folder = base_path
  else:
    dest_folder = '{0}/{1}'.format(base_path,
                                   os.path.relpath(path, input_base))
  return os.path.normpath(dest_folder)


def iota_exit(silent=False):
  if not silent:
    print '\n\nIOTA version {0}'.format(iota_version)
    print '{}\n'.format(now)
  sys.exit()
