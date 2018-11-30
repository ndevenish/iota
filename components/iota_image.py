from __future__ import division, print_function, absolute_import

"""
Author      : Lyubimov, A.Y.
Created     : 10/10/2014
Last Changed: 11/29/2018
Description : Subclasses image object and image importer from base classes.
"""

import numpy as np

import dxtbx
from dials.command_line.estimate_gain import estimate_gain

import iota.components.iota_utils as util
from iota.components.iota_base import SingleImageBase, ImageImporterBase


class SingleImage(SingleImageBase):  # For current cctbx.xfel
    def __init__(self, imgpath, idx=None):
        SingleImageBase.__init__(self, imgpath=imgpath, idx=idx)
        self.center_int = None
        self.gain = 1.0
        self.img_index = idx


class ImageImporter(ImageImporterBase):
    def __init__(self, init):
        ImageImporterBase.__init__(self, init=init)

    def instantiate_image_object(self, filepath, idx=None):
        """ Instantiate a SingleImage object for current backend
    :param filepath: path to image file
    """
        self.img_object = SingleImage(imgpath=filepath, idx=idx)

    def calculate_parameters(self, datablock=None):
        """ Image modification for current cctbx.xfel """

        if not datablock:
            # If data are given, apply modifications as specified below
            error = "IOTA IMPORT ERROR: Datablock not found!"
            return None, error
        else:
            error = []

            # Calculate auto-threshold
            # TODO: Revisit this; I REALLY don't like it.
            if self.iparams.cctbx_xfel.auto_threshold:
                beamX = self.img_object.final["beamX"]
                beamY = self.img_object.final["beamY"]
                px_size = self.img_object.final["pixel"]
                try:
                    img = dxtbx.load(self.img_object.img_path)
                    raw_data = img.get_raw_data()
                    beam_x_px = int(beamX / px_size)
                    beam_y_px = int(beamY / px_size)
                    data_array = raw_data.as_numpy_array().astype(float)
                    self.center_int = np.nanmax(
                        data_array[
                            beam_y_px - 20 : beam_y_px + 20,
                            beam_x_px - 20 : beam_x_px + 20,
                        ]
                    )
                except Exception as e:
                    error.append(
                        "IOTA IMPORT ERROR: Auto-threshold failed! {}".format(e)
                    )

            # Estimate gain (or set gain to 1.00 if cannot calculate)
            if self.iparams.image_import.estimate_gain:
                with util.Capturing() as junk_output:
                    try:
                        assert self.img_object.datablock  # Must have datablock here
                        imageset = self.img_object.datablock.extract_imagesets()[0]
                        self.img_object.gain = estimate_gain(imageset)
                    except Exception as e:
                        error.append(
                            "IOTA IMPORT ERROR: Estimate gain failed! ".format(e)
                        )

            # Collect error messages for logging
            if error:
                error_message = "\n".join(error)
            else:
                error_message = None

            return datablock, error_message


# **************************************************************************** #
