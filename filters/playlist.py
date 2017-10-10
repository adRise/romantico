#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import math
from os.path import abspath, dirname, isabs, join, splitext

import tornado.gen
from thumbor.filters import BaseFilter, filter_method
from thumbor.loaders import LoaderResult

TOTAL = 4
CANVAS_WIDTH = 430
CANVAS_HEIGHT = 249
CANVAS_BACKGROUND = '#3C3C42'
IMAGE_SPEC = [
    {
        'x': 5,
        'y': 5,
        'w': 165,
        'h': 239,
    },
    {
        'x': 175,
        'y': 5,
        'w': 165,
        'h': 239,
    },
    {
        'x': 345,
        'y': 5,
        'w': 80,
        'h': 117,
    },
    {
        'x': 345,
        'y': 127,
        'w': 80,
        'h': 117,
    },
]

# This code is a variant of filters/distributed_collage.py.
# usage: http://image_server//unsafe/filters:playlist(img1_url%7Cimg2_url%7Cimg3_url)/img0_url

class Picture:
    def __init__(self, url, thumbor_filter):
        self.url = url
        self.thumbor_filter = thumbor_filter
        self.extension = splitext(url)[-1].lower()
        self.engine = None
        self.fetched = False
        self.failed = False

    def fill_buffer(self, buffer):
        if (self.engine is None):
            self.engine = self.thumbor_filter.create_engine()
        self.buffer = buffer
        self.fetched = True

    def request(self):
        try:
            self.thumbor_filter.context.modules.loader.load(
                self.thumbor_filter.context, self.url, self.on_fetch_done)
        except Exception, err:
            self.error(err)

    def save_on_disc(self):
        if self.fetched:
            try:
                self.engine.load(self.buffer, self.extension)
            except Exception, err:
                self.error(err)

            try:
                self.thumbor_filter.storage.put(self.url, self.engine.read())
                self.thumbor_filter.storage.put_crypto(self.url)
            except Exception, err:
                self.error(err)
        else:
            self.error("Can't save unfetched image")

    def on_fetch_done(self, result):
        self.fill_buffer(result.buffer if isinstance(result, LoaderResult) else result)
        self.save_on_disc()
        self.thumbor_filter.on_image_fetch()

    # Resize image
    def process(self, width, height):
        try:
            self.engine.load(self.buffer, self.extension)
            self.engine.resize(width, height)
        except Exception, err:
            logging.error(err)

    def error(self, msg):
        logging.error(msg)
        self.failed = True

# Playlist filter. Stitches source images to generate new image.
# urls - Ordered list of source image URLs, separated by '|'
class Filter(BaseFilter):
    regex = (
        r'(?:playlist\((?P<urls>[^\)]+)\))'
    )

    @filter_method(
        BaseFilter.String,
        async=True
    )
    @tornado.gen.coroutine
    def playlist(self, callback, urls):
        logging.debug('playlist filter invoked')
        self.storage = self.context.modules.storage

        self.callback = callback
        self.urls = [self.context.request.image_url] + urls.split('|')
        self.urls = self.urls[:TOTAL]
        self.images = {}

        total = len(self.urls)
        if total < TOTAL:
            logging.warn('skip if total image is less thant %s' % TOTAL)
            callback()
        else:
            for url in self.urls:
                self.images[url] = Picture(url, self)

            # second loop needed to ensure that all images are in self.images
            # otherwise, self.on_image_fetch can call the self.assembly()
            # without that all images had being loaded
            for url in self.urls:
                buffer = yield tornado.gen.maybe_future(self.storage.get(url))
                pic = self.images[url]
                if buffer is not None:
                    pic.fill_buffer(buffer)
                    self.on_image_fetch()
                else:
                    pic.request()

    def is_all_fetched(self):
        return all([self.images[url].fetched for url in self.images])

    def is_any_failed(self):
        return any([self.images[url].failed for url in self.images])

    def create_engine(self):
        try:
            return self.context.modules.engine.__class__(self.context)
        except Exception, err:
            logging.error(err)

    def on_image_fetch(self):
        if (self.is_any_failed()):
            logging.error('some images failed')
            self.callback()
        elif self.is_all_fetched():
            self.assembly()

    def assembly(self):
        logging.debug('assembly started')
        canvas = self.create_engine()
        canvas.image = canvas.gen_image((CANVAS_WIDTH, CANVAS_HEIGHT), CANVAS_BACKGROUND)

        for i, url in enumerate(self.urls):
            # Resize and stitch images together
            try:
                image = self.images[url]
                image.process(IMAGE_SPEC[i]['w'], IMAGE_SPEC[i]['h'])
                canvas.paste(image.engine, (IMAGE_SPEC[i]['x'], IMAGE_SPEC[i]['y']), merge=True)
            except Exception, err:
                logging.error(err.message)

        self.engine.image = canvas.image
        logging.debug('assembled')
        self.callback()
