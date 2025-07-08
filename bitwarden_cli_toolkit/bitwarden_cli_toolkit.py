#! /usr/bin/env python3
#  -*- coding: utf-8 -*-
#
# This file is part of bitwarden_cli_toolkit, and is really just a binary shortcut to launch bitwarden_api_toolki.__main__

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))


from bitwarden_cli_toolkit.__main__ import main_gui

del sys.path[0]

if __name__ == "__main__":
    main_gui()
