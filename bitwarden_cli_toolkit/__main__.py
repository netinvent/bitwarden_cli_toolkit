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
    jobs: List[dict],
):
    """
    Apply permissions to collections.
    Args:
        jobs: list of {"name": str, "collection_ids": [UUID], "users": [...], "groups": [...]}
              Every job copies its users / groups permissions to its collection_ids.
    """
    total = sum(len(job["collection_ids"]) for job in jobs)
    layout = [
        [sg.Text("Inheriting permissions from parent collection...")],
        [sg.Text(f"0/{total} collections processed", key="progress_text")],
        [sg.Multiline(size=(80, 12), key="output", disabled=True)],
        [sg.Push(), sg.Button("Execute action"), sg.Button("Exit")],
    ]

    window = sg.Window(APP_NAME, layout, finalize=True)
    while True:
        event, values = window.read(timeout=100)
        if event == sg.WIN_CLOSED or event == "Exit":
            break

        if event == "Execute action":
            # Clear the output field
            window["output"].update(value="")
            has_failures = False
            processed = 0
            for job in jobs:
                window["output"].update(f"== {job['name']} ==\n", append=True)
                for collection_id in job["collection_ids"]:
                    try:
                        # Get the collection details
                        collection = cli.org_collection(
                            organization_id=organization_id, collection_id=collection_id
                        )
                        if not collection:
                            msg = f"Collection {collection_id} not found"
                            logger.error(msg)
                            window["output"].update(f"{msg}.\n", append=True)
                            has_failures = True
                        else:
                            logger.info(
                                f"Updating collection {collection_id} {collection['name']} with inherited permissions."
                            )
                            for kind in ("users", "groups"):
                                if not job[kind]:
                                    continue
                                if job.get("merge"):
                                    # Keep entries the child has on its own,
                                    # add / correct the ones of the parent
                                    merged = {
                                        entry["id"]: entry
                                        for entry in collection.get(kind) or []
                                    }
                                    merged.update(
                                        {entry["id"]: entry for entry in job[kind]}
                                    )
                                    collection[kind] = list(merged.values())
                                else:
                                    collection[kind] = job[kind]

                            if not cli.org_collection(
                                organization_id=organization_id,
                                collection_id=collection_id,
                                data=collection,
                            ):
                                msg = (
                                    f"Failed to update collection {collection['name']}"
                                )
                                logger.error(msg)
                                window["output"].update(f"{msg}\n", append=True)
                                has_failures = True
                            else:
                                window["output"].update(
                                    f"Updated collection {collection['name']} with users and groups.\n",
                                    append=True,
                                )
                    except Exception as exc:
                        msg = f"Error inheriting permissions for collection {collection_id}: {exc}"
                        logger.error(msg)
                        window["output"].update(f"{msg}\n", append=True)
                        has_failures = True
                    processed += 1
                    window["progress_text"].update(
                        f"{processed}/{total} collections processed"
                    )
                    window.refresh()
            if has_failures:
                sg.popup_error(
                    "Some collections failed to update. Check the output for details.",
                    keep_on_top=True,
                )
            else:
                sg.popup("All collections updated successfully.", keep_on_top=True)
            continue
    window.close()


def get_root_collections(collections: dict) -> dict:
    """
    Collections hierarchy is encoded in names (PARENT/CHILD/GRANDCHILD).
    Returns {root_id: {"name": str, "children": [ids of all descendants]}}
    for root collections (no "/" in name) that have at least one descendant.
    """
    roots = {}
    for col_id, name in collections.items():
        if "/" in name:
            continue
        children = [
            child_id
            for child_id, child_name in collections.items()
            if child_name.startswith(f"{name}/")
        ]
        if children:
            roots[col_id] = {"name": name, "children": children}
    return roots


def select_root_collections(roots: dict, preselected: List[UUID] = None):
    """
    Dialog with one checkbox per root collection.
    Returns the list of checked root ids, or None if cancelled.
    """
    preselected = preselected or []
    ordered = sorted(roots.items(), key=lambda item: item[1]["name"].lower())
    rows = [
        [
            sg.Checkbox(
                f"{root['name']}  ({len(root['children'])} sub-collections)",
                key=f"root_{root_id}",
                default=root_id in preselected,
            )
        ]
        for root_id, root in ordered
    ]
    layout = [
        [sg.Text("Select root (parent) collections")],
        [
            sg.Column(
                rows,
                scrollable=True,
                vertical_scroll_only=True,
                size=(520, 320),
                key="root_column",
            )
        ],
        [
            sg.Button("Select all", key="--ALL--"),
            sg.Button("Select none", key="--NONE--"),
            sg.Push(),
            sg.Button("OK"),
            sg.Button("Cancel"),
        ],
    ]
    window = sg.Window(APP_NAME, layout, keep_on_top=True, finalize=True)
    result = None
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, "Cancel"):
            break
        if event in ("--ALL--", "--NONE--"):
            for root_id, _ in ordered:
                window[f"root_{root_id}"].update(value=event == "--ALL--")
        if event == "OK":
            result = [root_id for root_id, _ in ordered if values[f"root_{root_id}"]]
            break
    window.close()
    return result


def _perm_map(entries) -> dict:
    return {
        entry["id"]: (
            bool(entry.get("readOnly")),
            bool(entry.get("hidePasswords")),
            bool(entry.get("manage")),
        )
        for entry in entries or []
    }


def compare_permissions(parent: dict, child: dict) -> dict:
    """
    Compare users / groups permissions of a parent collection against a child.
    Returns {"users": {"missing": [], "different": [], "extra": []}, "groups": {...}}
    Extra entries (only on child) are informational, they are not an error.
    """
    result = {}
    for kind in ("users", "groups"):
        parent_perms = _perm_map(parent.get(kind))
        child_perms = _perm_map(child.get(kind))
        result[kind] = {
            "missing": [i for i in parent_perms if i not in child_perms],
            "different": [
                i
                for i in parent_perms
                if i in child_perms and child_perms[i] != parent_perms[i]
            ],
            "extra": [i for i in child_perms if i not in parent_perms],
        }
    return result


def verify_roots(cli: BWCli, organization_id: UUID, roots: dict, root_ids):
    """
    Check that every descendant of the selected roots has all permissions of its root.
    Returns a list of per root results.
    """
    results = []
    for root_id in root_ids:
        root = roots[root_id]
        entry = {
            "name": root["name"],
            "total": len(root["children"]),
            "problems": [],
            "extras": [],
            "errors": [],
            "users": [],
            "groups": [],
        }
        results.append(entry)
        conf = cli.org_collection(
            organization_id=organization_id, collection_id=root_id
        )
        if not conf or "users" not in conf or "groups" not in conf:
            entry["root_error"] = True
            continue
        entry["users"] = conf["users"]
        entry["groups"] = conf["groups"]
        for child_id in root["children"]:
            child = cli.org_collection(
                organization_id=organization_id, collection_id=child_id
            )
            if not child:
                entry["errors"].append(child_id)
                continue
            diff = compare_permissions(conf, child)
            bad = any(diff[k]["missing"] or diff[k]["different"] for k in diff)
            if bad:
                entry["problems"].append(
                    {"id": child_id, "name": child["name"], "diff": diff}
                )
            elif any(diff[k]["extra"] for k in diff):
                entry["extras"].append(child["name"])
    return results


def format_verify_report(results: list) -> str:
    lines = []
    for entry in results:
        lines.append(f"== {entry['name']} ==")
        if entry.get("root_error"):
            lines.append("  Could not read root permissions")
            continue
        ok = entry["total"] - len(entry["problems"]) - len(entry["errors"])
        lines.append(
            f"  {ok}/{entry['total']} sub-collections OK, "
            f"{len(entry['problems'])} to fix, {len(entry['errors'])} unreadable"
        )
        for problem in entry["problems"]:
            parts = []
            for kind in ("users", "groups"):
                diff = problem["diff"][kind]
                if diff["missing"]:
                    parts.append(f"{len(diff['missing'])} {kind} missing")
                if diff["different"]:
                    parts.append(f"{len(diff['different'])} {kind} with other rights")
            lines.append(f"  - {problem['name']}: " + ", ".join(parts))
        for child_id in entry["errors"]:
            lines.append(f"  ! unreadable collection {child_id}")
        if entry["extras"]:
            lines.append(
                f"  (info: {len(entry['extras'])} OK sub-collections also have extra "
                "users/groups of their own)"
            )
    return "\n".join(lines)


def build_fix_jobs(results: list) -> list:
    return [
        {
            "name": entry["name"],
            "collection_ids": [problem["id"] for problem in entry["problems"]],
            "users": entry["users"],
            "groups": entry["groups"],
            "merge": True,
        }
        for entry in results
        if entry["problems"]
    ]


def build_root_jobs(cli: BWCli, organization_id: UUID, roots: dict, root_ids):
    """
    Fetch every selected root permissions, return (jobs, errors)
    """
    jobs = []
    errors = []
    for root_id in root_ids:
        conf = cli.org_collection(
            organization_id=organization_id, collection_id=root_id
        )
        if not conf or "users" not in conf or "groups" not in conf:
            errors.append(roots[root_id]["name"])
            continue
        jobs.append(
            {
                "name": roots[root_id]["name"],
                "collection_ids": roots[root_id]["children"],
                "users": conf["users"],
                "groups": conf["groups"],
            }
        )
    return jobs, errors


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

    single_tab = [
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
        ],
    ]
    roots_tab = [
        [
            sg.Text(
                "Every checked root collection passes its own user / group permissions\n"
                "to all of its sub-collections (children, grandchildren...)."
            )
        ],
        [sg.Button("Select root collections...", key="--SELECT_ROOTS--")],
        [
            sg.Text("Selected roots", size=(30, 1), key="roots_label"),
            sg.Multiline(size=(60, 12), key="roots_summary", disabled=True),
        ],
        [
            sg.Push(),
            sg.Button(
                "Inherit Permissions from selected roots", key="--INHERIT_ROOTS--"
            ),
        ],
    ]
    verify_tab = [
        [
            sg.Text(
                "Checks that every sub-collection of the selected root collections has\n"
                "all users / groups permissions of its root, and fixes only the ones that don't."
            )
        ],
        [
            sg.Button("Select root collections...", key="--SELECT_ROOTS_V--"),
            sg.Text("Selected roots: 0", key="verify_label", size=(30, 1)),
        ],
        [sg.Multiline(size=(90, 14), key="verify_report", disabled=True)],
        [
            sg.Push(),
            sg.Button("Verify", key="--VERIFY--"),
            sg.Button("Fix only mismatches", key="--FIX--", disabled=True),
        ],
    ]
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
            sg.TabGroup(
                [
                    [
                        sg.Tab("Single collection", single_tab),
                        sg.Tab("Root collections", roots_tab),
                        sg.Tab("Verify", verify_tab),
                    ]
                ]
            )
        ],
        [sg.Push(), sg.Button("Exit")],
    ]

    window = sg.Window(APP_NAME, layout)

    organization_id = None
    collection_conf = None
    child_collection_names = []
    child_collection_ids = []
    root_collections = {}
    selected_root_ids = []
    verify_results = []
    while True:
        event, values = window.read()
        if event == sg.WIN_CLOSED or event == "Exit":
            break
        if event in ("--SELECT_ROOTS--", "--SELECT_ROOTS_V--"):
            if not organization_id or not root_collections:
                sg.popup_error(
                    "Please select an organization with root collections first.",
                    keep_on_top=True,
                )
                continue
            chosen = select_root_collections(root_collections, selected_root_ids)
            if chosen is not None:
                selected_root_ids = chosen
                verify_results = []
                window["--FIX--"].update(disabled=True)
                window["verify_report"].update(value="")
                window["verify_label"].update(f"Selected roots: {len(chosen)}")
                window["roots_label"].update(f"Selected roots: {len(chosen)}")
                window["roots_summary"].update(
                    value="\n".join(
                        f"{root_collections[root_id]['name']} "
                        f"({len(root_collections[root_id]['children'])} sub-collections)"
                        for root_id in chosen
                    )
                )
        if event == "--VERIFY--":
            if not organization_id or not selected_root_ids:
                sg.popup_error(
                    "Please select an organization and at least one root collection.",
                    keep_on_top=True,
                )
                continue
            verify_results = minimal_gui_thread_runner(
                "Verifying permissions",
                verify_roots,
                cli,
                organization_id,
                root_collections,
                selected_root_ids,
            )
            window["verify_report"].update(value=format_verify_report(verify_results))
            window["--FIX--"].update(disabled=not build_fix_jobs(verify_results))
            if not build_fix_jobs(verify_results):
                sg.popup("Nothing to fix.", keep_on_top=True)
        if event == "--FIX--":
            jobs = build_fix_jobs(verify_results)
            if not jobs:
                continue
            total = sum(len(job["collection_ids"]) for job in jobs)
            if (
                sg.popup_yes_no(
                    f"Add the missing permissions to {total} sub-collections?\n"
                    "Their own extra users / groups are kept.",
                    keep_on_top=True,
                )
                != "Yes"
            ):
                continue
            with HideWindow(window):
                inherit_permissions(cli, organization_id=organization_id, jobs=jobs)
            window["--FIX--"].update(disabled=True)
            window["verify_report"].update(
                value="Fix executed, run Verify again to confirm."
            )
            verify_results = []
        if event == "--INHERIT_ROOTS--":
            if not organization_id or not selected_root_ids:
                sg.popup_error(
                    "Please select an organization and at least one root collection.",
                    keep_on_top=True,
                )
                continue
            jobs, errors = minimal_gui_thread_runner(
                "Getting root collections permissions",
                build_root_jobs,
                cli,
                organization_id,
                root_collections,
                selected_root_ids,
            )
            if errors:
                sg.popup_error(
                    "Could not read permissions of: " + ", ".join(errors),
                    keep_on_top=True,
                )
            if not jobs:
                continue
            total = sum(len(job["collection_ids"]) for job in jobs)
            if (
                sg.popup_yes_no(
                    f"Overwrite permissions of {total} sub-collections "
                    f"from {len(jobs)} root collection(s)?",
                    keep_on_top=True,
                )
                != "Yes"
            ):
                continue
            with HideWindow(window):
                inherit_permissions(cli, organization_id=organization_id, jobs=jobs)
        if event == "org_name":
            org_name = values["org_name"]
            organization_id = get_key_from_value(objects["organizations"], org_name)
            objects["collections"].clear()
            root_collections = {}
            selected_root_ids = []
            window["roots_summary"].update(value="")
            window["roots_label"].update("Selected roots")
            verify_results = []
            window["verify_label"].update("Selected roots: 0")
            window["verify_report"].update(value="")
            window["--FIX--"].update(disabled=True)
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
                root_collections = get_root_collections(objects["collections"])
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
                        jobs=[
                            {
                                "name": values["collection_name"],
                                "collection_ids": child_collection_ids,
                                "users": user_permissions,
                                "groups": group_permissions,
                            }
                        ],
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
