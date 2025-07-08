#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of bitwarden_cli_toolkit

__intname__ = "bitwarden_cli_toolkit.secret_keys"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2023-2025 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2025070701"


# NPF-SEC-00011: Default AES key obfuscation


def obfuscation(key: bytes) -> bytes:
    """
    Symmetric obfuscation of bytes
    """
    if key:
        keyword = b"/*bitwarden_cli_toolkit 2025*/"
        key_length = len(keyword)
        return bytes(c ^ keyword[i % key_length] for i, c in enumerate(key))
    return key
