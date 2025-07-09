#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of bitwarden_cli_toolkit

__intname__ = "bitwarden_cli_toolkit.secret_keys"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2025 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2025070801"

import os
from uuid import UUID
import sys
from pathlib import Path
from typing import List
import json
import FreeSimpleGUI as sg
from ofunctions.misc import get_key_from_value
from ofunctions.logger_utils import logger_get_logger
from bitwarden_cli_toolkit.configuration import (
    load_config,
    save_config,
    get_default_config,
)
from bitwarden_cli_toolkit.helpers import HideWindow, minimal_gui_thread_runner
from bitwarden_cli_toolkit.bwcli_wrapper import BWCli
from bitwarden_cli_toolkit.__version__ import __version__

logger = logger_get_logger("bitwarden_cli_toolkit.log")

APP_NAME = (
    "Bitwarden CLI toolkit - Collection Permission Inheritor" + f" v{__version__}"
)
sg.theme("Reddit")  # Set the theme for the GUI


def inherit_permissions(
    cli: BWCli,
    organization_id: UUID,
    collection_ids: List[UUID],
    user_permissions,
    group_permissions,
):
    layout = [
        [sg.Text("Inheriting permissions from parent collection...")],
        [
            sg.Text(
                f"0/{len(collection_ids)} collections processed", key="progress_text"
            )
        ],
        [sg.Multiline(size=(80, 12), key="output", disabled=True)],
        [sg.Push(), sg.Button("Execute action"), sg.Button("Exit")],
    ]

    window = sg.Window(APP_NAME, layout, finalize=True)
    index = 0
    while True:
        event, values = window.read(timeout=100)
        if event == sg.WIN_CLOSED or event == "Exit":
            break

        if event == "Execute action":
            # Clear the output field
            window["output"].update(value="")
            has_failures = False
            for index, collection_id in enumerate(collection_ids):
                try:
                    # Get the collection details
                    collection = cli.org_collection(
                        organization_id=organization_id, collection_id=collection_id
                    )
                    if not collection:
                        msg = f"Collection {collection_id} not found"
                        logger.error(msg)
                        window["output"].update(f"{msg}.\n", append=True)
                        continue
                    logger.info(
                        f"Updating collection {collection_id} {collection['name']} with inherited permissions."
                    )

                    if user_permissions:
                        collection["users"] = user_permissions
                    if group_permissions:
                        collection["groups"] = group_permissions

                    if not cli.org_collection(
                        organization_id=organization_id,
                        collection_id=collection_id,
                        data=collection,
                    ):
                        msg = f"Failed to update collection {collection['name']}"
                        logger.error(msg)
                        window["output"].update(
                            f"{msg}\n",
                            append=True,
                        )
                        has_failures = True
                        continue
                    else:
                        window["output"].update(
                            f"Updated collection {collection['name']} with users and groups.\n",
                            append=True,
                        )
                except Exception as exc:
                    msg = f"Error inheriting permissions for collection {collection_id}: {exc}"
                    logger.error(msg)
                    window["output"].update(f"{msg}\n", append=True)
                window["progress_text"].update(
                    f"{index +1 }/{len(collection_ids)} collections processed"
                )
                window.refresh()
            if index >= len(collection_ids) - 1:
                if has_failures:
                    sg.popup_error(
                        "Some collections failed to update. Check the output for details.",
                        keep_on_top=True,
                    )
                else:
                    sg.popup("All collections updated successfully.", keep_on_top=True)
            continue
    window.close()


def inheritor_gui(cli: BWCli):
    """
    GUI for inheriting permissions from collections to items.
    Args:
        cli (BWCli): An instance of the Bitwarden CLI class.
    """
    objects = {
        "organizations": {},
        "collections": {},
    }
    organizations = minimal_gui_thread_runner(
        "Getting organizations", cli.organizations
    )
    if not organizations:
        sg.popup_error(
            "Failed to retrieve organizations. Check logs for details.",
            keep_on_top=True,
        )
        return False
    else:
        for org in cli.organizations():
            objects["organizations"][org["id"]] = org["name"]

    layout = [
        [sg.Text("Bitwarden Collection Permission Inheritor")],
        [
            sg.Text("Select Organization:", size=(30, 1)),
            sg.InputCombo(
                list(objects["organizations"].values()),
                key="org_name",
                enable_events=True,
                size=(60, 1),
            ),
        ],
        [
            sg.Text("Select Collection:", size=(30, 1)),
            sg.InputCombo([], key="collection_name", enable_events=True, size=(60, 1)),
        ],
        [
            sg.Text("Children", size=(30, 1), key="children"),
            sg.Multiline(
                size=(60, 5), key="item_name", enable_events=True, disabled=True
            ),
        ],
        [
            sg.Text("Collection user permissions", size=(30, 1), key="users"),
            sg.Multiline(size=(60, 5), key="collection_user_permissions"),
        ],
        [
            sg.Text("Collection group permissions", size=(30, 1), key="groups"),
            sg.Multiline(size=(60, 5), key="collection_group_permissions"),
        ],
        [
            sg.Push(),
            sg.Button("Inherit Permissions to all children", key="--INHERIT--"),
            sg.Button("Exit"),
        ],
    ]

    window = sg.Window(APP_NAME, layout)

    organization_id = None
    collection_conf = None
    child_collection_names = []
    child_collection_ids = []
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == "Exit":
            break
        if event == "org_name":
            org_name = values["org_name"]
            organization_id = get_key_from_value(objects["organizations"], org_name)
            if organization_id:
                # Update collection list based on selected organization
                collections = minimal_gui_thread_runner(
                    "Getting collections",
                    cli.org_collections,
                    organization_id=organization_id,
                )
                if not collections:
                    sg.popup_error(
                        "Failed to retrieve collections. Check logs for details.",
                        keep_on_top=True,
                    )
                    continue
                for col in collections:
                    objects["collections"][col["id"]] = col["name"]
                window["collection_name"].update(
                    values=list(objects["collections"].values())
                )
        if event == "collection_name":
            child_collection_names = []
            child_collection_ids = []
            collection_name = values["collection_name"]
            for collection in objects["collections"].values():
                if collection.startswith(f"{collection_name}/"):
                    col_id = get_key_from_value(objects["collections"], collection)
                    child_collection_names.append(objects["collections"][col_id])
                    child_collection_ids.append(col_id)
            window["children"].Update(f"Children: {len(child_collection_names)}")
            window["item_name"].update(value="\n".join(child_collection_names))
            current_collection_id = get_key_from_value(
                objects["collections"], collection_name
            )
            collection_conf = minimal_gui_thread_runner(
                "Getting collection configuration",
                cli.org_collection,
                organization_id=organization_id,
                collection_id=current_collection_id,
            )
            try:
                window["collection_user_permissions"].update(
                    value=json.dumps(collection_conf["users"], indent=2)
                )
                window["users"].update(
                    value=f"Collection user permissions: {len(collection_conf['users'])}"
                )
            except KeyError:
                sg.popup_error(
                    "Failed to retrieve collection user permissions. Check logs for details.",
                    keep_on_top=True,
                )
            try:
                window["collection_group_permissions"].update(
                    value=json.dumps(collection_conf["groups"], indent=2)
                )
                window["groups"].update(
                    value=f"Collection group permissions: {len(collection_conf['groups'])}"
                )
            except KeyError:
                sg.popup_error(
                    "Failed to retrieve collection group permissions. Check logs for details.",
                    keep_on_top=True,
                )
        if event == "--INHERIT--":
            if organization_id and child_collection_ids and collection_conf:
                try:
                    user_permissions = json.loads(
                        values["collection_user_permissions"].strip()
                    )
                except json.JSONDecodeError as exc:
                    sg.popup_error(
                        f"Invalid JSON in user permissions: {exc}",
                        keep_on_top=True,
                    )
                    continue
                try:
                    group_permissions = json.loads(
                        values["collection_group_permissions"].strip()
                    )
                except json.JSONDecodeError as exc:
                    sg.popup_error(
                        f"Invalid JSON in group permissions: {exc}",
                        keep_on_top=True,
                    )
                    continue
                with HideWindow(window):
                    inherit_permissions(
                        cli,
                        organization_id=organization_id,
                        collection_ids=child_collection_ids,
                        user_permissions=user_permissions,
                        group_permissions=group_permissions,
                    )
            else:
                sg.popup_error(
                    "Please select an organization and a collection with child collections.",
                    keep_on_top=True,
                )
    window.close()


def main_gui():
    """
    Main function to run the GUI.
    """
    config_file = Path("bitwarden_cli_toolkit_config.yaml")
    try:
        if os.path.isfile(config_file):
            logger.info(f"Loading configuration from {config_file}")
            # Load the configuration from the file
            config = load_config(config_file)
        else:
            config = get_default_config()
    except OSError:
        logger.info(f"No configuration file found in {config_file}, using defaults")
        config = get_default_config()

    layout = [
        [sg.Text("Bitwarden CLI Toolkit")],
        [
            sg.Text("Server URL:", size=(30, 1)),
            sg.InputText(config.g("admin_api.url"), key="server_url"),
        ],
        [
            sg.Text("Username", size=(30, 1)),
            sg.InputText(config.g("admin_api.credentials.username"), key="username"),
        ],
        [
            sg.Text("Password", size=(30, 1)),
            sg.InputText(
                config.g("admin_api.credentials.password"),
                key="password",
                password_char="*",
            ),
        ],
        # [sg.Text("Or using API credentials")],
        # [sg.Text("Client ID:", size=(30, 1)), sg.InputText(config.g("admin_api.credentials.client_id"), key='client_id')],
        # [sg.Text("Client Secret:", size=(30, 1)), sg.InputText(config.g("admin_api.credentials.client_secret"), key='client_secret', password_char='*')],
        [
            sg.Text("Path to bw executable:", size=(30, 1)),
            sg.InputText(config.g("admin_api.bw_executable"), key="bw_executable"),
            sg.FileBrowse("Browse", target="bw_executable"),
        ],
        [sg.Checkbox("Run with REST API", key="use_rest", default=True)],
        [sg.Push(), sg.Button("Login"), sg.Button("Save config"), sg.Button("Exit")],
    ]

    window = sg.Window(APP_NAME, layout)

    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == "Exit":
            break
        if event == "Login":
            username = values["username"]
            password = values["password"]
            # client_id = values['client_id']
            # client_secret = values['client_secret']
            server_url = values["server_url"]
            bw_executable = values["bw_executable"]
            use_rest = values["use_rest"]
            if (not username or not password) or not server_url or not bw_executable:
                sg.popup_error("Please enter requested information.", keep_on_top=True)
                continue
            try:
                cli = BWCli(
                    username=username,
                    password=password,
                    bw_executable=bw_executable,
                    use_rest=use_rest,
                )
                result = minimal_gui_thread_runner(
                    "Configuring bw cli", cli.config, server_url=server_url
                )
                if not result:
                    sg.popup_error(
                        f"Failed to configure Bitwarden CLI with server URL: {server_url}",
                        keep_on_top=True,
                    )
                    continue
            except FileNotFoundError:
                sg.popup_error(
                    f"Bitwarden CLI executable not found at {bw_executable}. Please check the path.",
                    keep_on_top=True,
                )
                continue
            result = minimal_gui_thread_runner("Logging in", cli.login_as_user)
            if result:
                with HideWindow(window):
                    inheritor_gui(cli)
            else:
                sg.popup_error(
                    "Login failed. Check logs for details.", keep_on_top=True
                )
        if event == "Save config":
            # Save the configuration to a file
            config.s("admin_api.url", values["server_url"])
            config.s("admin_api.credentials.username", values["username"])
            config.s("admin_api.credentials.password", values["password"])
            # config.s("admin_api.credentials.client_id", values['client_id'])
            # config.s("admin_api.credentials.client_secret", values['client_secret'])
            config.s("admin_api.bw_executable", values["bw_executable"])
            config.s("admin_api.use_rest", values["use_rest"])
            try:
                save_config(config_file, config)
                sg.popup("Configuration saved successfully!", keep_on_top=True)
            except Exception as exc:
                sg.popup_error(f"Failed to save configuration: {exc}", keep_on_top=True)
    window.close()


if __name__ == "__main__":
    try:
        main_gui()
    except KeyboardInterrupt as exc:
        logger.error(f"Program interrupted by keyboard: {exc}")
        logger.debug("Trace:", exc_info=True)
        # EXIT_CODE 200 = keyboard interrupt
        sys.exit(200)
    except Exception as exc:
        sg.popup(
            f"Unknown error, please see log file for further info: {exc}",
            keep_on_top=True,
        )
        logger.critical(f"GUI Execution error {exc}")
        logger.info("Trace:", exc_info=True)
        sys.exit(251)
