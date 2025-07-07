#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of bitwarden_cli_toolkit

__intname__ = "bitwarden_api_toolkit.secret_keys"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2025 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2025070701"


import os
from pathlib import Path
from command_runner import command_runner
import json
from uuid import UUID
from logging import getLogger


logger = getLogger()


class BWCli:
    """
    A class to interact with the Bitwarden CLI.
    """

    def __init__(
        self, username: str, password: str, session=None, bw_executable: str = None
    ):
        if not bw_executable:
            if os.name == "nt":
                self.bw_executable = "bw.exe"
            else:
                self.bw_executable = "bw"
        else:
            if os.name == "nt":
                self.bw_executable = bw_executable.replace("/", "\\")
            else:
                self.bw_executable = bw_executable
        if not Path(self.bw_executable).is_file():
            logger.error(f"Bitwarden CLI executable not found: {self.bw_executable}")
            raise FileNotFoundError(
                f"Bitwarden CLI executable not found: {self.bw_executable}"
            )
        self.session = session
        self.username = username
        self.password = password

    def run(self, args, with_session=True, raw=False):
        """
        Run a Bitwarden CLI command.
        Args:
            args (list): List of arguments for the bw command.
            with_session (bool): Whether to include the session in the command.
        Returns:
            str: The output of the command.
        """
        if with_session and self.session:
            os.environ["BW_SESSION"] = self.session
            logger.debug(
                "No session provided or session is None, running without session."
            )
        exit_code, output = command_runner(
            [self.bw_executable] + args, shell=True, encoding="utf-8"
        )
        if self.session:
            os.environ.pop(
                "BW_SESSION", None
            )  # Clean up the session variable after use so we don't leak
        if exit_code == 0:
            try:
                return json.loads(output) if not raw else output
            except json.JSONDecodeError:
                logger.error(
                    "Failed to decode JSON output from Bitwarden CLI command. Output was:."
                )
                logger.error(output)
                return None
        else:
            logger.error(
                f"Bitwarden CLI command failed with exit code {exit_code}. Output was:"
            )
            logger.error(output)
            return None

    def status(self) -> bool:
        """
        Check the status of the Bitwarden CLI.
        Returns:
            Optional bool:
            True if unlocked
            False if locked
            None if unauthenticated or error
        """
        status = self.run(["status"])
        if status:
            if status["status"] == "locked":
                logger.info("Bitwarden CLI is locked.")
                return False
            if status["status"] == "unlocked":
                logger.info("Bitwarden CLI is unlocked.")
                return True
            if status["status"] == "unauthenticated":
                logger.info("Bitwarden CLI is unauthenticated.")
                return None
        return None

    def config(self, host=None):
        """
        Get or set the Bitwarden CLI configuration.
        Args:
            host (str): The host to set in the configuration.
        Returns:
            dict: The current configuration or None if setting a host.
        """
        if self.status():
            self.logout()
        args = ["config", "server"]
        if host:
            args.append(host)
            return self.run(args, raw=True)
        return self.run(args)

    def logout(self):
        """
        Log out of the Bitwarden CLI.
        Returns:
            bool: True if logout was successful, False otherwise.
        """
        result = self.run(["logout"], raw=True)
        if result:
            logger.info("Logged out successfully.")
            self.session = None
            return True
        else:
            logger.error("Logout failed.")
            return False

    def unlock(self):
        """
        Unlock the Bitwarden CLI.
        Returns:
            bool: True if unlock was successful, False otherwise.
        """

        result = self.run(["unlock", "--raw", self.password], raw=True)
        if result:
            self.session = result.strip()
            logger.info("Unlocked successfully.")
            return True
        else:
            logger.error("Unlock failed.")
            return False

    def login_as_user(self):
        """
        Log in to the Bitwarden CLI.
        Returns:
            bool: True if login was successful, False otherwise.
        """
        status = self.status()
        if status is True:
            logger.info("Already logged in.")
            return True
        elif status is None:
            logger.info("Not authenticated, logging in.")
            self.session = None
        elif status is False:
            logger.info("Bitwarden CLI is locked, unlocking.")
            if self.unlock():
                return True

        args = ["login", "--raw"]
        if self.username:
            args.append(self.username)
        if self.password:
            args.append(self.password)
        result = self.run(args, raw=True)
        if result:
            self.session = result.strip()
            logger.info(f"Logged in successfully. Session key: {self.session}")
            return True
        else:
            logger.error("Login failed.")
            return False

    def login_as_api(self, client_id, client_secret):
        """
        Log in to the Bitwarden CLI using API key.
        Args:
            client_id (str): The API client ID.
            client_secret (str): The API client secret.
        Returns:
            bool: True if login was successful, False otherwise.
        """
        if self.status():
            logger.info("Already logged in.")
            return True
        args = ["login", "--apikey", "--raw"]
        if client_id:
            args.append(client_id)
        if client_secret:
            args.append(client_secret)
        result = self.run(args, raw=True)
        if result:
            self.session = result.strip()
            logger.info(
                f"Logged in successfully with API key. Session key: {self.session}"
            )
            return True
        else:
            logger.error("Login with API key failed.")
            return False

    def list(self, objects="items", search=None, org_id=None, folder_id=None):
        """
        List Bitwarden objects.
        Args:
            objects (str): The type of objects to list (e.g., 'items', 'collections').
            search (str): Optional search term to filter results.
        Returns:
            list: A list of Bitwarden objects.
        """
        args = ["list", objects]
        if search:
            args.append(f"--search={search}")
        if org_id:
            args.append(f"--organizationid={org_id}")
        if folder_id:
            args.append(f"--folderid={folder_id}")
        return self.run(args)

    def get(
        self, object_type="item", object_id: UUID = None, organization_id: UUID = None
    ):
        """
        item, username, password, uri, totp, notes, exposed, attachment, folder, collection, org-collection, organization, template, fingerprint, send
        """
        args = ["get", object_type, object_id]
        if organization_id:
            args.append(f"--organizationid={organization_id}")
        return self.run(args)

    def encode(self, data: dict):
        """
        Encode data for Bitwarden CLI.
        Args:
            data (dict): The data to encode.
        Returns:
            str: The encoded data.
        """
        if isinstance(data, dict):
            data = json.dumps(data, separators=(",", ":"))

        # bw encode will fail if we pass a list of args, so we pass a single string
        # command_runner will fail if we pass a linux path in windows, eg C:/somepath/bw.exe
        args = " ".join(["echo", data, "|", self.bw_executable, "encode"])
        exit_code, output = command_runner(args, shell=True, encoding="utf-8")
        if exit_code == 0:
            return output.strip()

    def edit(
        self,
        object_type="item",
        object_id: UUID = None,
        organization_id: UUID = None,
        data: dict = None,
    ):
        # We need to encode the data json via bw encode first
        data = self.encode(data)
        args = ["edit", object_type, object_id]
        if organization_id:
            args.append(f"--organizationid={organization_id}")
        args.append(data)
        return self.run(args)

    def organizations(self, name: str = None):
        """
        List Bitwarden organizations.
        Returns:
            list: A list of Bitwarden organizations.
        """
        return self.list(objects="organizations", search=name)

    def collections(self, name: str = None):
        """
        List Bitwarden collections.
        Returns:
            list: A list of Bitwarden collections.
        """
        return self.list(objects="collections", search=name)

    def collection(self, id_collection: UUID):
        """
        Get a specific Bitwarden collection by ID.
        Args:
            id (UUID): The ID of the collection to retrieve.
        Returns:
            dict: The Bitwarden collection details.
        """
        args = ["get", "collection", str(id_collection)]
        return self.run(args)

    def items(self, name: str = None):
        """
        List Bitwarden items.
        Returns:
            list: A list of Bitwarden items.
        """
        return self.list(objects="items", search=name)

    def org_collections(self, org_id: UUID, name: str = None):
        """
        List Bitwarden organization collections.
        Returns:
            list: A list of Bitwarden organization collections.
        """
        return self.list(objects="org-collections", org_id=org_id, search=name)

    def org_collection(self, org_id: UUID, collection_id: UUID, data: dict = None):
        """
        Get a specific Bitwarden organization collection by ID.
        Args:
            org_id (UUID): The ID of the organization.
            collection_id (UUID): The ID of the collection to retrieve.
        Returns:
            dict: The Bitwarden organization collection details.
        """
        if data:
            return self.edit(
                "org-collection",
                object_id=collection_id,
                organization_id=org_id,
                data=data,
            )
        return self.get(
            "org-collection", object_id=collection_id, organization_id=org_id
        )

    def org_members(self, org_id: UUID, name: str = None):
        """
        List Bitwarden organization members.
        Returns:
            list: A list of Bitwarden organization members.
        """
        return self.list(objects="org-members", org_id=org_id, search=name)

    def folders(self, name: str = None):
        """
        List Bitwarden folders.
        Returns:
            list: A list of Bitwarden folders.
        """
        return self.list(objects="folders", search=name)


if __name__ == "__main__":
    # Example usage
    cli = BWCli(username="some@user.tld", password="somepassword")
    if cli.login_as_user():
        print("Logged in successfully.")
        orgs = cli.organizations()
        if orgs:
            print("Organizations:", orgs)
            collections = cli.org_collections(
                name="SOME COLLECTION", org_id=orgs[0]["id"]
            )
            if collections:
                print("Collections:", collections)
                col = cli.org_collection(
                    org_id=orgs[0]["id"], collection_id=collections[0]["id"]
                )
                # Updating collection (nothing changed)
                cli.org_collection(
                    org_id=orgs[0]["id"], collection_id=collections[0]["id"], data=col
                )
