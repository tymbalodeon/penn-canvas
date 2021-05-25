# API calls to canvas
# baowei@upenn.edu
# Oct 12, 2020

import os
import sys
from canvasapi import Canvas
from canvas_shared import *

API_URL = "https://canvas.upenn.edu/"

canvas = Canvas(API_URL, API_KEY_PROD)
course = canvas.get_course(1527342)
modules = course.get_modules()

for m in modules:
    if m.id == 2334986:
        m.relock()
