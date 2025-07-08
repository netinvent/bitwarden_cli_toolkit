#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of bitwarden_cli_toolkit

__intname__ = "bitwarden_api_toolkit.secret_keys"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2025 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2025070701"


# Encryption key to keep repo settings safe in plain text yaml config file

# This is the default key that comes with Vaultwarden API Toolkit.. You should change it (and keep a backup copy in case you need to decrypt a config file data)
# Obtain a new key with:
# python3 -c "from cryptidy import symmetric_encryption as s; print(s.generate_key())"
# You may also create a new keyfile via
# bitwarden_cli_toolkit-cli --create-key keyfile.key
# Given keyfile can then be loaded via environment variables, see documentation for more

AES_KEY = b"\xdc\xbdw\x18\x19\x95\xa2\xad\xa1\xf6\xfe\xf4\x9d\xf4\xb8\xea\xc0JC\xc0\xe4kf\xb1\xc7\t\x7f2\x9du?\xff"
