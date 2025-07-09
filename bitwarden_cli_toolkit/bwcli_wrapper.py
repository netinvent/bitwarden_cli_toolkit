#! /usr/bin/env python
#  -*- coding: utf-8 -*-
#
# This file is part of bitwarden_cli_toolkit

__intname__ = "bitwarden_cli_toolkit.secret_keys"
__author__ = "Orsiris de Jong"
__copyright__ = "Copyright (C) 2025 NetInvent"
__license__ = "GPL-3.0-only"
__build__ = "2025070901"


import os
from pathlib import Path
import json
from uuid import UUID
from logging import getLogger
import subprocess
import atexit
from command_runner import command_runner
from ofunctions.requestor import Requestor
from ofunctions.threading import threaded
from ofunctions.process import kill_childs

logger = getLogger()


class BWCli:
    """
    A class to interact with the Bitwarden CLI.
    """

    def __init__(
        self,
        username: str,
        password: str,
        session=None,
        bw_executable: str = None,
        use_rest: bool = False,
        host: str = "localhost",
        port: int = 8087,
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
        self._session = session
        self._username = username
        self._password = password
        self.use_rest = use_rest
        self._host = host
        self._port = port
        self._rest_is_running = False
        if self.use_rest:
            self._requestor = Requestor(servers=[f"http://{self._host}:{self._port}"])
            self._must_stop = False

    def must_shutdown(self):
        return self._must_stop

    @threaded
    def run_server(self):
        """
        Runs bw-cli in server mode to allow REST API access.
        """
        if self._session:
            os.environ["BW_SESSION"] = self._session
            logger.debug(
                "No session provided or session is None, running without session."
            )
        if not self.use_rest:
            logger.info("Bitwarden CLI REST API access is not enabled.")
            return False
        if self._rest_is_running:
            logger.info("Bitwarden CLI server is already running.")
            return True
        process = subprocess.Popen(
            [
                self.bw_executable,
                "serve",
                "--hostname",
                self._host,
                "--port",
                str(self._port),
            ],
        )
        logger.info(
            f"Launching Bitwarden CLI server with pid {process.pid} on {self._host}:{self._port}"
        )
        self._rest_is_running = True
        if self._session:
            os.environ.pop(
                "BW_SESSION", None
            )  # Clean up the session variable after use so we don't leak
        atexit.register(kill_childs, process.pid, itself=True)

    def run_as_rest(self, path, data=None):
        if not self._requestor.api_session:
            # bw executable has authentication, so we don't need to authenticate here
            self._requestor.create_session(endpoint="/status", authenticated=False)
        if data:
            action = "update"
        else:
            action = "read"
        result = self._requestor.requestor(endpoint=path, action=action, data=data)

        # Returns objects like
        # {'success': True, 'data': {'object': 'list', 'data': [{'object': 'organization', 'id': 'abcdefg0-0000-1111-2222-12345678901234', 'name': 'SOME ORG', 'status': 2, 'type': 0, 'enabled': True}]}}
        # {'success': True, 'data': {'object': 'org-collection', 'id': 'gfedcba0-9999-8888-7777-43210987654321', 'organizationId': 'abcdefg0-0000-1111-2222-12345678901234', 'name': 'COLLB/COLD', 'externalId': None, 'groups': [{'id': '26c47fd0-f37d-4c0d-81f7-1af0dccf7471', 'readOnly': True, 'hidePasswords': False, 'manage': False}],
        if result:
            if result["success"] is True:
                if result["data"]["object"] == "list":
                    return result["data"]["data"]
                if result["data"]["object"] in [
                    "item",
                    "username",
                    "password",
                    "uri",
                    "totp",
                    "notes",
                    "exposed",
                    "attachment",
                    "folder",
                    "collection",
                    "org-collection",
                    "organization",
                    "template",
                    "fingerprint",
                    "send",
                ]:
                    return result["data"]
            else:
                logger.error(
                    f"Bitwarden CLI REST API command failed with error: {result}"
                )
                return None
        else:
            logger.error("Bitwarden CLI REST API command returned no result.")
            return None

    def run(self, args, with_session=True, raw=False):
        """
        Run a Bitwarden CLI command.
        Args:
            args (list): List of arguments for the bw command.
            with_session (bool): Whether to include the session in the command.
        Returns:
            str: The output of the command.
        """
        if with_session and self._session:
            os.environ["BW_SESSION"] = self._session
            logger.debug(
                "No session provided or session is None, running without session."
            )
        exit_code, output = command_runner(
            [self.bw_executable] + args, shell=True, encoding="utf-8"
        )
        if self._session:
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

    def config(self, server_url=None):
        """
        Get or set the Bitwarden CLI configuration.
        Args:
            host (str): The host to set in the configuration.
        Returns:
            dict: The current configuration or None if setting a host.
        """
        if self.status() in [False, True]:
            self.logout()
        args = ["config", "server"]
        if server_url:
            args.append(server_url)
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
            self._session = None
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

        result = self.run(["unlock", "--raw", self._password], raw=True)
        if result:
            self._session = result.strip()
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
            if not self.run_server():
                logger.error("Failed to start Bitwarden CLI server.")
                return False
            return True
        elif status is None:
            logger.info("Not authenticated, logging in.")
            self._session = None
        elif status is False:
            logger.info("Bitwarden CLI is locked, unlocking.")
            if self.unlock():
                if not self.run_server():
                    logger.error("Failed to start Bitwarden CLI server.")
                    return False
                return True

        args = ["login", "--raw"]
        if self._username:
            args.append(self._username)
        if self._password:
            args.append(self._password)
        result = self.run(args, raw=True)
        if result:
            self._session = result.strip()
            logger.info(f"Logged in successfully. Session key: {self._session}")
            if not self.run_server():
                logger.error("Failed to start Bitwarden CLI server.")
                return False
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
            self._session = result.strip()
            logger.info(
                f"Logged in successfully with API key*. We now have a session key"
            )
            return True
        else:
            logger.error("Login with API key failed.")
            return False

    def list(self, objects="items", search=None, organization_id=None, folder_id=None):
        """
        List Bitwarden objects.
        Args:
            objects (str): The type of objects to list (e.g., 'items', 'collections').
            search (str): Optional search term to filter results.
        Returns:
            list: A list of Bitwarden objects.
        """

        if self.use_rest:
            path = f"/list/object/{objects}/?"
            query = []
            if organization_id:
                query.append(f"organizationId={organization_id}")
            if search:
                query.append(f"/?search={search}")
            if folder_id:
                query.append(f"folderId={folder_id}")
            if query:
                path += "&".join(query)

            return self.run_as_rest(path=path)

        args = ["list", objects]
        if search:
            args.append(f"--search={search}")
        if organization_id:
            args.append(f"--organizationid={organization_id}")
        if folder_id:
            args.append(f"--folderid={folder_id}")
        return self.run(args=args)

    def get(
        self, object_type="item", object_id: UUID = None, organization_id: UUID = None
    ):
        """
        item, username, password, uri, totp, notes, exposed, attachment, folder, collection, org-collection, organization, template, fingerprint, send
        """
        if self.use_rest:
            path = f"/object/{object_type}/{object_id}/?"
            query = []
            if organization_id:
                query.append(f"organizationId={organization_id}")
            path += "&".join(query)

            return self.run_as_rest(path=path)

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
        if self.use_rest:
            path = f"/object/{object_type}/{object_id}/?"
            query = []
            if object_id:
                query.append(f"id={object_id}")
            if organization_id:
                query.append(f"organizationId={organization_id}")
            path += "&".join(query)

            return self.run_as_rest(path=path, data=data)

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

    def org_collections(self, organization_id: UUID, name: str = None):
        """
        List Bitwarden organization collections.
        Returns:
            list: A list of Bitwarden organization collections.
        """
        return self.list(
            objects="org-collections", organization_id=organization_id, search=name
        )

    def org_collection(
        self, organization_id: UUID, collection_id: UUID, data: dict = None
    ):
        """
        Get a specific Bitwarden organization collection by ID.
        Args:
            organization_id (UUID): The ID of the organization.
            collection_id (UUID): The ID of the collection to retrieve.
        Returns:
            dict: The Bitwarden organization collection details.
        """
        if data:
            return self.edit(
                "org-collection",
                object_id=collection_id,
                organization_id=organization_id,
                data=data,
            )
        return self.get(
            "org-collection", object_id=collection_id, organization_id=organization_id
        )

    def org_members(self, organization_id: UUID, name: str = None):
        """
        List Bitwarden organization members.
        Returns:
            list: A list of Bitwarden organization members.
        """
        return self.list(
            objects="org-members", organization_id=organization_id, search=name
        )

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
                name="SOME COLLECTION", organization_id=orgs[0]["id"]
            )
            if collections:
                print("Collections:", collections)
                col = cli.org_collection(
                    organization_id=orgs[0]["id"], collection_id=collections[0]["id"]
                )
                # Updating collection (nothing changed)
                cli.org_collection(
                    organization_id=orgs[0]["id"],
                    collection_id=collections[0]["id"],
                    data=col,
                )
