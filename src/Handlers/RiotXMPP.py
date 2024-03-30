import asyncio
import base64
import json
import ssl
from typing import Dict
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from src.exceptions import AuthFailure
from . import logger


class RiotXMMPClient:
    """
    A class to act as a client for the Riot XMPP servers.

    ...

    Attributes:
    ----------
    * other attributes are initialized in init method

    Methods
    -------
    get_stream_element() -> bytes:
        Returns the stream element
    get_rso_auth() -> bytes:
        Returns the authentication for RSO
    get_bind_request() -> bytes:
        Returns the bind request element
    get_entitlement_request() -> bytes:
        Returns the entitlement request element
    get_session_request() -> bytes:
        Returns session request element
    async connect():
        Initiates the connection to the Riot XMPP server
    async start_auth_flow():
        Starts the authentication flow
    async process_presences():
        Processes incoming XMPP presences
    async send(message: bytes):
        Sends a message to the server
    async recv_until(seperator: bytes) -> str:
        Receives messages until a given separator
    async close():
        Closes the connection
    """

    def __init__(
        self,
        credentials: Dict[str, str],
        chat_host: str,
        chat_port: int,
        region: str,
        puuid: str,
    ) -> None:
        """Initializes the RiotXMPP object."""
        self.reader = None
        self.writer = None
        self.logger = logger
        self.rso_token = credentials["rso_token"]
        self.pas_token = credentials["pas_token"]
        self.entitlements_token = credentials["entitlements_token"]
        self.stream_ns = "http://etherx.jabber.org/streams"
        self.region = region
        self.default_ns = "jabber:client"
        self.default_lang = "en"
        self.chat_host = chat_host
        self.chat_port = chat_port
        self.puuid = puuid
        self.connected = False
        self.context = ssl.create_default_context()
        self.context.check_hostname = True
        self.context.verify_mode = ssl.CERT_REQUIRED

    def get_stream_element(self) -> bytes:
        """Returns the stream element in byte format."""

        stream = rf'<?xml version="1.0" encoding="UTF-8"?><stream:stream to="{self.region}.pvp.net" xml:lang="{self.default_lang}" version="1.0" xmlns="{self.default_ns}" xmlns:stream="{self.stream_ns}">'
        return stream.encode(encoding="UTF-8")

    def get_rso_auth(self) -> bytes:
        """Returns the RSO authentication element in byte format."""

        auth = Element(
            "auth",
            attrib={
                "mechanism": "X-Riot-RSO-PAS",
                "xmlns": "urn:ietf:params:xml:ns:xmpp-sasl",
            },
        )
        rso_token_elem = Element("rso_token")
        rso_token_elem.text = self.rso_token
        pas_token_elem = Element("pas_token")
        pas_token_elem.text = self.pas_token
        auth.append(rso_token_elem)
        auth.append(pas_token_elem)
        return ElementTree.tostring(auth, encoding="utf-8")

    @staticmethod
    def get_bind_request() -> bytes:
        """Returns the bind request element in byte format."""

        iq_element = Element("iq", attrib={"id": "_xmpp_bind1", "type": "set"})
        bind_element = Element(
            "bind", attrib={"xmlns": "urn:ietf:params:xml:ns:xmpp-bind"}
        )

        puuid_element = Element("puuid-mode", attrib={"enabled": "true"})

        iq_element.append(bind_element)

        bind_element.append(puuid_element)

        return ElementTree.tostring(iq_element, encoding="utf-8")

    def get_entitlement_request(self) -> bytes:
        """Returns the entitlements request element in byte format."""

        iq_element = Element("iq", attrib={"id": "xmpp_entitlements_0", "type": "set"})
        entitlements_element = Element(
            "entitlements", attrib={"xmlns": "urn:riotgames:entitlements"}
        )
        token_element = Element("token")
        token_element.text = self.entitlements_token
        iq_element.append(entitlements_element)
        entitlements_element.append(token_element)
        return ElementTree.tostring(iq_element, encoding="utf-8")

    @staticmethod
    def get_session_request() -> bytes:
        """Returns the session request element in byte format."""

        iq_element = Element("iq", attrib={"id": "_xmpp_session1", "type": "set"})
        session_element = Element(
            "session", attrib={"xmlns": "urn:ietf:params:xml:ns:xmpp-session"}
        )
        platform_element = Element("platform")
        platform_element.text = "riot"
        iq_element.append(session_element)
        session_element.append(platform_element)
        return ElementTree.tostring(iq_element, encoding="utf-8")

    async def connect(self):
        """Establishes the connection to the server."""
        self.connected = True
        try:
            self.logger.info(f"Connecting to {self.chat_host}...")
            self.reader, self.writer = await asyncio.open_connection(
                host=self.chat_host, port=self.chat_port, ssl=self.context
            )
            self.logger.success(
                f"Successfully connected to {self.chat_host} on port {self.chat_port}"
            )
        except Exception as e:
            self.connected = False
            self.logger.error(f"Failed to connect: {e}")

    async def start_auth_flow(self):
        """Starts the authentication flow for the XMPP client."""
        auth_flow = [
            {
                "stanza": self.get_stream_element(),
                "seperator": b"</stream:features>",
                "stage": "stream element",
            },
            {
                "stanza": self.get_rso_auth(),
                "seperator": b"</success>",
                "stage": "RSO auth element",
            },
            {
                "stanza": self.get_stream_element(),
                "seperator": b"</stream:features>",
                "stage": "stream element",
            },
            {
                "stanza": self.get_bind_request(),
                "seperator": b"</bind></iq>",
                "stage": "bind element",
            },
            {
                "stanza": self.get_entitlement_request(),
                "seperator": b"></iq>",
                "stage": "entitlement element",
            },
            {
                "stanza": self.get_session_request(),
                "seperator": b"</session></iq>",
                "stage": "session element",
            },
        ]

        # Start the auth flow
        try:
            for item in auth_flow:
                self.logger.info(f"Sending {item['stage']}...")
                await self.send(item["stanza"])
                response = await self.recv_until(item["seperator"])
                if response:
                    if "<fail" in response:
                        raise AuthFailure(response)
                    else:
                        self.logger.log("RESPONSE", f"\n{response}\n")
        except Exception as e:
            self.logger.exception(f"Authentication flow failed:\n{e}")
            await self.close()

    def decode_presence(self, presence: str):
        if presence[:9] != "<presence":
            self.logger.debug(
                f"Skipping decoding presence: presence does not begin with '<presence>'"
            )
            return None
        root = ElementTree.fromstring(presence)
        try:
            games = root.find("games")
            if games is not None:
                valorant = games.find("valorant")
                if valorant is not None:
                    p = valorant.find("p")
                    if p is not None:
                        b64_data = p.text
                        decoded_data = base64.b64decode(b64_data).decode("utf-8")
                        formatted_data = json.loads(decoded_data)
                        return formatted_data
        except Exception as e:
            self.logger.warning(f"Could not decode presence: {e}")
            pass

    async def process_presences(self, decode: bool = False):
        """Processes incoming XMPP messages."""

        # Loop through to read the socket endlessly
        if self.connected is False:
            self.logger.log(
                "ERROR", "Failed to start processing: connection is not established"
            )
            return
        else:
            self.logger.info("Sending <presence/>...")
            await self.send(message=b"<presence/>")
            self.logger.info("Starting presence processing loop...")
            while True:
                try:
                    presence = await self.recv_until(b"</presence>")
                    # If there's no messages/presences to process, sleep for 2 seconds and try again
                    if not presence or len(presence.strip()) < 10:
                        await asyncio.sleep(2)
                        continue
                    else:
                        self.logger.log("RESPONSE", f"\n{presence}")
                        if decode is True:
                            decode_data = self.decode_presence(presence)
                            if decode_data is not None:
                                self.logger.log(
                                    "DECODED", f"\n{json.dumps(decode_data, indent=4)}"
                                )
                            else:
                                self.logger.log(
                                    "DECODED",
                                    f"No presence data to decode in response\n",
                                )

                except asyncio.exceptions.IncompleteReadError:
                    self.logger.warning("Shutting down...")
                    break

    async def send(self, message: bytes):
        """Sends a message to the server.

        Args:
            message (bytes): The message to be sent to the server.
        """
        self.logger.log("REQUEST", f"\n{message.decode('utf-8')}\n")
        self.writer.write(message)
        await self.writer.drain()

    async def recv_until(self, seperator: bytes) -> str:
        """Receives messages until a given separator is reached.

        Args:
            seperator (bytes): The separator.

        Returns:
            str: The incoming message from the server.
        """
        try:
            # Determining if request failed. Probably not the best way to do this but it works.
            msg = await self.reader.read(7)
            status = msg.decode("utf-8")
            if "<fail" in status:
                msg = await self.reader.readuntil(b"</failure>")
                msg = msg.decode("utf-8")
                return f"{status}{msg}"
            else:
                msg = await self.reader.readuntil(separator=seperator)
                msg = msg.decode("utf-8")
                return f"{status}{msg}"

        except asyncio.exceptions.CancelledError:
            await self.close()

    async def close(self):
        """Closes the XMPP client connection."""
        self.connected = False
        self.logger.warning("Closing connection...")
        self.writer.close()
        await self.writer.wait_closed()
