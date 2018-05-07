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

        # Convert PNG to JPEG.
        if img.format.upper() != 'PNG':
          return buffer

        out = cStringIO.StringIO()
        if img.mode == 'P' or img.mode == 'RGBA':
            img = img.convert('RGB')
        options = {
            'optimize': True
        }
        if self.context.config.PROGRESSIVE_JPEG:
            options['progressive'] = True
        img.save(out, format='JPEG', **options)
        out.seek(0)

        return out.getvalue()
