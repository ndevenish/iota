from __future__ import division
# LIBTBX_SET_DISPATCHER_NAME iota.process

'''
Author      : Lyubimov, A.Y.
Created     : 07/26/2014
Last Changed: 08/17/2016
Description : IOTA image processing submission module
'''

import os
from libtbx.easy_mp import parallel_map
from libtbx import easy_pickle as ep

import iota.components.iota_image as img

class ProcessImage():
  ''' Wrapper class to do full processing of an image '''
  def __init__(self, init, input_entry, input_type = 'image'):
    self.init = init
    self.input_entry = input_entry
    self.input_type = input_type

  def run(self):
    img_object = None
    if self.input_type == 'image':
      img_object = img.SingleImage(self.input_entry, self.init)
      img_object.import_image()
      print 'DEBUG: Imported image'
    elif self.input_type == 'object':
      img_object = self.input_entry[2]
      img_object.import_int_file(self.init)

    if self.init.params.image_conversion.convert_only:
      return img_object
    else:
      img_object.process()
      #result_file = os.path.splitext(img_object.obj_file)[0] + '.fin'
      #ep.dump(result_file, img_object)
      return img_object

class ProcessAll():
  def __init__(self,
               init,
               iterable,
               input_type='image'):
    self.init = ep.load(init)
    self.iterable = ep.load(iterable)
    self.type = input_type

  def run(self):
    parallel_map(iterable=self.iterable,
                 func = self.full_proc_wrapper,
                 #callback = self.callback,
                 processes=self.init.params.n_processors)

    end_filename = os.path.join(self.init.tmp_base, 'finish.cfg')
    with open(end_filename, 'w') as ef:
      ef.write('')

  # def callback(self, result):
  #   print "*****", result, "*****"
  #   if result is not None:
  #     result_file = result.obj_file.split('.')[0] + '.fin'
  #     ep.dump(result_file, result)

  def full_proc_wrapper(self, input_entry):
    print 'Processing {}'.format(input_entry[2])
    proc_image_instance = ProcessImage(self.init, input_entry, self.type)
    proc_image_instance.run()


def parse_command_args():
  """ Parses command line arguments (only options for now) """
  parser = argparse.ArgumentParser(prog='iota.process')
  parser.add_argument('init', type=str, default=None,
                      help='Path to init file')
  parser.add_argument('--files', type=str, nargs='?', const=None, default=None,
                      help='Specify input file list')
  parser.add_argument('--type', type=str, nargs='?', const=None,
                      default='image',
                      help='Specify input type')
  return parser

# ============================================================================ #
if __name__ == "__main__":
  import argparse
  args, unk_args = parse_command_args().parse_known_args()

  proc = ProcessAll(init=args.init, iterable=args.files, input_type=args.type)
  proc.run()
