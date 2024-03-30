import base64
import os
import sys
from typing import Literal
import httpx
import psutil
from src.exceptions import AuthFailure
from . import logger


class ValorantAuth:
    """
    Constructor for the ValorantAuth class.

    :param auth_type: The type of authentication to be used, either "local" or "remote".
    :type auth_type: Literal["local", "remote"]

    :raises ValueError: If the authentication type is not a valid value.
    """

    def __init__(self, auth_type: Literal["local", "remote"] = "local"):
        """
        Constructor for the ValorantAuth class.
        """
        self.logger = logger
        match auth_type.lower():
            case "local":
                if self._is_riot_process_running():
                    self.lockfile_keys = ["name", "PID", "port", "password", "protocol"]
                    self.lockfile_path = os.path.join(
                        os.getenv("LOCALAPPDATA"),
                        R"Riot Games\Riot Client\Config\lockfile",
                    )
                    self.lockfile_data = self._get_lockfile()
                    self.local_headers = self._get_local_headers()
                    self.tokens = self.get_tokens()
                    if self.tokens is None:
                        return
                    self.user_info = self.get_user_info()
            case "remote":
                raise NotImplementedError
            case _:
                raise ValueError(f"'{auth_type}' is not a valid authentication type.")

    def _is_riot_process_running(self) -> bool:
        """
        Check if Riot Client is running
        """

        # Iterate over all running processes
        proc_list = []
        client_names = ["RiotClientServices.exe", "Riot Client.exe", "VALORANT.exe"]
        for proc in psutil.process_iter(["name"]):
            proc_list.append(str(proc.name()).lower())
        # Check if Riot Client is running
        for client_name in client_names:
            if client_name.lower() in proc_list:
                self.logger.debug(f"Riot Client running: {client_name}")
                return True
            else:
                self.logger.error(
                    f"Riot Client (RiotClientServices.exe) is not running"
                )
                return False

    def _get_lockfile(self) -> dict | None:
        """
        This is a method to get the lockfile data
        """
        try:
            with open(self.lockfile_path) as lockfile:
                data = lockfile.read().split(":")
                self.logger.success("Acquired lockfile data")
                return dict(zip(self.lockfile_keys, data))
        except FileNotFoundError as e:
            self.logger.error(e)
        except Exception as e:
            self.logger.error(f"Unexpected error occurred while getting lockfile: {e}")
        return None

    def _get_local_headers(self) -> dict:
        """
        Create headers for local requests
        """
        local_auth = f"riot:{self.lockfile_data['password']}"
        local_headers = {
            "Authorization": f"Basic {base64.b64encode(local_auth.encode()).decode()}"
        }
        return local_headers

    def get_tokens(self) -> dict | None:
        """
        Get auth tokens from local endpoints
        """
        client = httpx.Client(verify=False)
        try:
            response = client.get(
                f"https://127.0.0.1:{self.lockfile_data['port']}/rso-auth/v1/authorization",
                headers=self.local_headers,
            )
            if response.status_code != 200:
                raise AuthFailure("Not authenticated")
            self.logger.success(f"Authentication check passed")
            entitlements_data = client.get(
                f"https://127.0.0.1:{self.lockfile_data['port']}/entitlements/v2/token",
                headers=self.local_headers,
            )
            entitlements_data = entitlements_data.json()

            rso_token = entitlements_data["authorization"]["accessToken"]["token"]
            entitlements_token = entitlements_data["token"]
            id_token = entitlements_data["authorization"]["idToken"]["token"]

            pas_token_request_headers = {"Authorization": f"Bearer {rso_token}"}
            pas_token_data = client.get(
                "https://riot-geo.pas.si.riotgames.com/pas/v1/service/chat",
                headers=pas_token_request_headers,
            )
            pas_token = str(pas_token_data.content.decode("utf-8"))

            return {
                "rso_token": rso_token,
                "entitlements_token": entitlements_token,
                "pas_token": pas_token,
                "id_token": id_token,
            }
        except AuthFailure as e:
            self.logger.error(f"Authentication error: {e}")
            return None
        finally:
            client.close()

    def get_user_info(self):
        """
        Get information on authenticated user
        """
        client = httpx.Client(verify=False)
        try:
            response = client.get(
                f"https://127.0.0.1:{self.lockfile_data['port']}/chat/v1/session",
                headers=self.local_headers,
            )
            if response.status_code != 200:
                self.logger.error(response.status_code)
                raise AuthFailure("Not authenticated to in game chat")
            user_info = response.json()
            user_info["game_name"] = f"{user_info['game_name']}#{user_info['game_tag']}"
            affinity_info = client.put(
                "https://riot-geo.pas.si.riotgames.com/pas/v1/product/valorant",
                headers={"Authorization": f"Bearer {self.tokens['rso_token']}"},
                json={"id_token": self.tokens["id_token"]},
            ).json()

            user_info["affinity_region"] = affinity_info["affinities"]["live"]

            shards_map = {
                "latam": "na",
                "br": "na",
                "na": "na",
                "pbe": "na",
                "eu": "eu",
                "ap": "ap",
                "kr": "kr",
            }
            user_info["affinity_shard"] = shards_map[
                affinity_info["affinities"]["live"]
            ]
            user_chat_config = client.get(
                f"https://127.0.0.1:{self.lockfile_data['port']}/client-config/v2/namespace/chat",
                headers=self.local_headers,
            ).json()

            user_info["chat_host"] = user_chat_config["chat.host"]
            user_info["chat_port"] = user_chat_config["chat.port"]
            return user_info
        except AuthFailure as e:
            self.logger.error(f"Authentication failure: {e}")
            return None
        finally:
            client.close()
