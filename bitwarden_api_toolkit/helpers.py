#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of bitwarden_cli_toolkit

__intname__ = "bitwarden_api_toolkit.helpers"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2025 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2025070302"


from typing import Callable, Union
from logging import getLogger
from time import sleep
import threading
from concurrent.futures import Future
import FreeSimpleGUI as sg
from bitwarden_api_toolkit.__debug__ import _DEBUG

logger = getLogger()


sg.theme("Reddit")


# For debugging purposes, we should be able to disable threading to see actual errors
# out of thread
if not _DEBUG:
    USE_THREADING = True
else:
    USE_THREADING = False
    logger.info("Running without threads as per debug requirements")

# Seconds between screen refreshes
UPDATE_INTERVAL = 1
# Seconds between total average speed updates
TOTAL_AVERAGE_INTERVAL = 5


def minimal_gui_thread_runner(
    message: str,
    fn: Union[Callable, str],
    *args,
    **kwargs,
):
    def call_with_future(fn, future, args, kwargs):
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)

    future = Future()
    thread = threading.Thread(target=call_with_future, args=(fn, future, args, kwargs))
    thread.daemon = True
    thread.start()
    while not future.done() and not future.cancelled():
        sg.PopupAnimated(
            sg.DEFAULT_BASE64_LOADING_GIF,
            message=message,
            time_between_frames=50,
            # background_color=BG_COLOR_LDR,
            # text_color=TXT_COLOR_LDR,
        )
        sleep(0.1)
    sg.PopupAnimated(None)
    return future.result()


class HideWindow:
    """
    Context manager to hide a window when a new one is opened
    This prevents showing blocked windows
    """

    def __init__(self, window):
        self.window = window

    def __enter__(self):
        self.window.hide()

    def __exit__(self, exc_type, exc_value, traceback):
        # exit method receives optional traceback from execution within with statement
        self.window.un_hide()
