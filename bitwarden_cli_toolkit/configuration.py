#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of bitwarden_cli_toolkit

__intname__ = "bitwarden_api_toolkit.configuration"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2025 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2025070801"


from typing import Optional, List, Any, Union
import sys
import os
from copy import deepcopy
from pathlib import Path
import zlib
from logging import getLogger
from ruamel.yaml import YAML
from ruamel.yaml.compat import ordereddict
from ruamel.yaml.comments import CommentedMap
from packaging.version import parse as version_parse, InvalidVersion
from cryptidy import symmetric_encryption as enc
from ofunctions.misc import replace_in_iterable
from bitwarden_cli_toolkit.key_management import AES_KEY, get_aes_key
from bitwarden_cli_toolkit.__version__ import __version__ as MAX_CONF_VERSION

MIN_MIGRATABLE_CONF_VERSION = "0.0.1"
MIN_CONF_VERSION = "0.0.1"


sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))


logger = getLogger()
opt_aes_key, msg = get_aes_key()
if opt_aes_key:
    logger.info(msg)
    AES_KEY = opt_aes_key
elif opt_aes_key is False:
    logger.critical(msg)


# Monkeypatching ruamel.yaml ordreddict so we get to use pseudo dot notations
# eg data.g('my.array.keys') == data['my']['array']['keys']
# and data.s('my.array.keys', 'new_value')
def g(self, path, sep=".", default=None, list_ok=False):
    """
    Getter for dot notation in an a dict/OrderedDict
    print(d.g('my.array.keys'))
    """
    try:
        return self.mlget(path.split(sep), default=default, list_ok=list_ok)
    except AssertionError as exc:
        logger.debug(
            f"CONFIG ERROR {exc} for path={path},sep={sep},default={default},list_ok={list_ok}"
        )
        raise AssertionError from exc


def s(self, path, value, sep="."):
    """
    Setter for dot notation in a dict/OrderedDict
    d.s('my.array.keys', 'new_value')
    """
    data = self
    keys = path.split(sep)
    lastkey = keys[-1]
    for key in keys[:-1]:
        data = data[key]
    data[lastkey] = value


def d(self, path, sep="."):
    """
    Deletion for dot notation in a dict/OrderedDict
    d.d('my.array.keys')
    """
    try:
        data = self
        keys = path.split(sep)
        lastkey = keys[-1]
        for key in keys[:-1]:
            data = data[key]
        data.pop(lastkey)
    except KeyError:
        # We don't care deleting non existent keys ^^
        pass


ordereddict.g = g
ordereddict.s = s
ordereddict.d = d

ID_STRING = "__BITWARDEN_API_TOOLKIT__"

# NPF-SEC-00003: Avoid password command divulgation
ENCRYPTED_OPTIONS = [
    "admin_api.credentials.password",
    "admin_api.credentials.client_secret",
]

# This is what a config file looks like
empty_config_dict = {
    "conf_version": MAX_CONF_VERSION,
    "admin_api": {
        "url": "https://vault.bitwarden.com",
        "credentials": {
            "username": None,
            "password": None,
            "client_id": None,
            "client_secret": None,
            "api_key": None,  # API key is used for Bitwarden CLI
            "api_key_id": None,  # API key ID is used for Bitwarden CLI
        },
        "bw_executable": "bw.exe" if os.name == "nt" else "bw",
        "use_rest": True,
    },
}


def convert_to_commented_map(
    source_dict,
):
    if isinstance(source_dict, dict):
        return CommentedMap(
            {k: convert_to_commented_map(v) for k, v in source_dict.items()}
        )
    return source_dict


def get_default_config() -> dict:
    """
    Returns a config dict as nested CommentedMaps (used by ruamel.yaml to keep comments intact)
    """
    full_config = deepcopy(empty_config_dict)

    return convert_to_commented_map(full_config)


def key_should_be_encrypted(key: str, encrypted_options: List[str]):
    """
    Checks whether key should be encrypted
    """
    if key:
        for option in encrypted_options:
            if option in key:
                return True
    return False


def crypt_config(
    full_config: dict, aes_key: str, encrypted_options: List[str], operation: str
):
    try:

        def _crypt_config(key: str, value: Any) -> Any:
            if key_should_be_encrypted(key, encrypted_options):
                if value is not None:
                    if operation == "encrypt":
                        if (
                            isinstance(value, str)
                            and (
                                not value.startswith(ID_STRING)
                                or not value.endswith(ID_STRING)
                            )
                        ) or not isinstance(value, str):
                            value = enc.encrypt_message_hf(
                                value, aes_key, ID_STRING, ID_STRING
                            ).decode("utf-8")
                    elif operation == "decrypt":
                        if (
                            isinstance(value, str)
                            and value.startswith(ID_STRING)
                            and value.endswith(ID_STRING)
                        ):
                            _, value = enc.decrypt_message_hf(
                                value,
                                aes_key,
                                ID_STRING,
                                ID_STRING,
                            )
                    else:
                        raise ValueError(f"Bogus operation {operation} given")
            return value

        return replace_in_iterable(
            full_config,
            _crypt_config,
            callable_wants_key=True,
            callable_wants_root_key=True,
        )
    except Exception as exc:
        logger.error(f"Cannot {operation} configuration: {exc}.")
        logger.debug("Trace:", exc_info=True)
        return False


def is_encrypted(full_config: dict) -> bool:
    is_encrypted = True

    def _is_encrypted(key, value) -> Any:
        nonlocal is_encrypted

        if key_should_be_encrypted(key, ENCRYPTED_OPTIONS):
            if value is not None:
                if isinstance(value, str) and (
                    not value.startswith(ID_STRING) or not value.endswith(ID_STRING)
                ):
                    is_encrypted = False
        return value

    replace_in_iterable(
        full_config,
        _is_encrypted,
        callable_wants_key=True,
        callable_wants_root_key=True,
    )
    return is_encrypted


def _get_config_file_checksum(config_file: Path) -> str:
    """
    It's nice to log checksums of config file to see whenever it was changed
    """
    with open(config_file, "rb") as fh:
        cur_hash = 0
        while True:
            s = fh.read(65536)
            if not s:
                break
            cur_hash = zlib.crc32(s, cur_hash)
        return "%08X" % (cur_hash & 0xFFFFFFFF)


def _load_config_file(config_file: Path) -> Union[bool, dict]:
    """
    Checks whether config file is valid
    """
    try:
        with open(config_file, "r", encoding="utf-8") as file_handle:
            yaml = YAML(typ="rt")
            full_config = yaml.load(file_handle)
            if not full_config:
                logger.critical(f"Config file {config_file} seems empty !")
                return False
            try:
                conf_version = version_parse(str(full_config.g("conf_version")))
                if not conf_version:
                    logger.critical(
                        f"Config file {config_file} has no configuration version. Is this a valid bitwarden_cli_toolkit config file?"
                    )
                    return False
                if conf_version < version_parse(
                    MIN_MIGRATABLE_CONF_VERSION
                ) or conf_version > version_parse(MAX_CONF_VERSION):
                    logger.critical(
                        f"Config file version {str(conf_version)} is not in required version range min={MIN_MIGRATABLE_CONF_VERSION}, max={MAX_CONF_VERSION}"
                    )
                    return False
                """
                if conf_version < version_parse(MIN_CONF_VERSION):
                    full_config = _migrate_config_dict(
                        full_config, str(conf_version), MIN_CONF_VERSION
                    )
                    logger.info("Writing migrated config file")
                    save_config(config_file, full_config)
                """
            except (AttributeError, TypeError, InvalidVersion) as exc:
                logger.critical(
                    f"Cannot read conf version from config file {config_file}, which seems bogus: {exc}"
                )
                logger.debug("Trace:", exc_info=True)
                return False
            logger.info(
                f"Loaded config {_get_config_file_checksum(config_file)} in {config_file.absolute()}"
            )
            return full_config
    except OSError as exc:
        logger.critical(f"Cannot load configuration file from {config_file}: {exc}")
        logger.debug("Trace:", exc_info=True)
        return False


def load_config(config_file: Path) -> Optional[dict]:
    full_config = _load_config_file(config_file)
    if not full_config:
        return None
    config_file_is_updated = False

    # Check if we need to encrypt some variables
    if not is_encrypted(full_config):
        logger.info("Encrypting non encrypted data in configuration file")
        config_file_is_updated = True
    # Decrypt variables
    full_config = crypt_config(
        full_config, AES_KEY, ENCRYPTED_OPTIONS, operation="decrypt"
    )
    if full_config is False:
        msg = "Cannot decrypt config file"
        logger.critical(msg)
        raise EnvironmentError(msg)

    # save config file if needed
    if config_file_is_updated:
        logger.info("Updating config file")
        save_config(config_file, full_config)
    return full_config


def save_config(config_file: Path, full_config: dict) -> bool:
    try:
        with open(config_file, "w", encoding="utf-8") as file_handle:
            if not is_encrypted(full_config):
                full_config = crypt_config(
                    full_config, AES_KEY, ENCRYPTED_OPTIONS, operation="encrypt"
                )
            yaml = YAML(typ="rt")
            yaml.dump(full_config, file_handle)
        # Since yaml is a "pointer object", we need to decrypt after saving
        full_config = crypt_config(
            full_config, AES_KEY, ENCRYPTED_OPTIONS, operation="decrypt"
        )
        logger.info(f"Saved configuration file {config_file}")
        return True
    except OSError as exc:
        logger.critical(f"Cannot save configuration file to {config_file}: {exc}")
        return False
