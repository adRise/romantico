#!/usr/bin/python
# -*- coding: utf-8 -*-

from thumbor.optimizers import BaseOptimizer
from thumbor.utils import logger
from PIL import Image
import cStringIO

class Optimizer(BaseOptimizer):

    def should_run(self, image_extension, buffer):
        img = Image.open(cStringIO.StringIO(buffer))
        logger.warn('Image format is %s', img.format)
        return True


    def run_optimizer(self, image_extension, buffer):
        img = Image.open(cStringIO.StringIO(buffer))
        logger.info('Image format is %s', img.format)
        if img.format.upper() not in ('JPEG', 'JPG', 'PNG'):
          return buffer

        out = cStringIO.StringIO()

        if img.mode == 'P':
            img = img.convert('RGB')

        img.save(out, format='JPEG', optimize=True)
        out.seek(0)
        return out.getvalue()
