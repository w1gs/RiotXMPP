import asyncio
import ssl
from typing import Dict
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

# from ValApi import ValApi


class RiotXMMP:

    def __init__(self, credentials: Dict[str, str], region='na1'):
        self.rso_token = credentials['rso_token']
        self.pas_token = credentials['pas_token']
        self.entitlements_token = credentials['entitlements_token']
        self.stream_ns = 'http://etherx.jabber.org/streams'
        self.region = region
        self.default_ns = 'jabber:client'
        self.default_lang = 'en'

    def get_stream_header(self):
        stream_header = '<stream:stream to="%s" %s %s %s %s>' % (
            f'{self.region}.pvp.net',
            'xmlns:stream="%s"' % self.stream_ns,
            'xmlns="%s"' % self.default_ns,
            'xml:lang="%s"' % self.default_lang,
            'version="1.0"',
        )
        return stream_header

    def get_rso_auth(self):
        auth = Element(
            'auth',
            attrib={
                'mechanism': 'X-Riot-RSO-PAS',
                'xmlns': 'urn:ietf:params:xml:ns:xmpp-sasl',
            },
        )
        rso_token_elem = Element('rso_token')
        rso_token_elem.text = self.rso_token
        pas_token_elem = Element('pas_token')
        pas_token_elem.text = self.pas_token
        auth.append(rso_token_elem)
        auth.append(pas_token_elem)
        return ElementTree.tostring(auth, encoding='utf-8')

    def get_bind_request(self):
        iq_element = Element('iq', attrib={'id': '_xmpp_bind1', 'type': 'set'})
        bind_element = Element(
            'bind', attrib={'xmlns': 'urn:ietf:params:xml:ns:xmpp-bind'}
        )
        puuid_element = Element('puuid-mode', attrib={'enabled': 'true'})
        iq_element.append(bind_element)
        bind_element.append(puuid_element)
        return ElementTree.tostring(iq_element, encoding='utf-8')

    def get_entititlement_request(self):
        iq_element = Element('iq', attrib={'id': 'xmpp_entitlements_0', 'type': 'set'})
        entitlements_element = Element(
            'entitlements', attrib={'xmlns': 'urn:riotgames:entitlements'}
        )
        token_element = Element('token')
        token_element.text = self.entitlements_token
        iq_element.append(entitlements_element)
        entitlements_element.append(token_element)
        return ElementTree.tostring(iq_element, encoding='utf-8')

    def get_session_request(self):
        iq_element = Element('iq', attrib={'id': '_xmpp_session1', 'type': 'set'})
        session_element = Element(
            'session', attrib={'xmlns': 'urn:ietf:params:xml:ns:xmpp-session'}
        )
        platform_element = Element('platform')
        platform_element.text = 'riot'
        iq_element.append(session_element)
        session_element.append(platform_element)
        return ElementTree.tostring(iq_element, encoding='utf-8')

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(
            'br.chat.si.riotgames.com', 5223, ssl=context
        )

    async def send(self, message: str):
        print(f'Sending: {message}')
        self.writer.write(message.encode('utf-8'))
        await self.writer.drain()

    async def recv(self):
        msg = await self.reader.read(4024)
        print(f"Response:\n {msg.decode('utf-8')}")

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

    async def handle_communication(self):
        while True:
            try:
                await self.recv()
            except KeyboardInterrupt:
                break
        await self.close()


context = ssl.create_default_context()


async def main():
    # ValApi is just a custom class to handle grabbing creds from lockfile
    v = ValApi()
    creds = v.get_tokens()
    rso = RiotXMMP(credentials=creds, region='br1')

    await rso.connect()

    header = rso.get_stream_header()
    auth = rso.get_rso_auth()
    bind = rso.get_bind_request()
    ent = rso.get_entititlement_request()
    sesh = rso.get_session_request()

    print('Sending stream header...')
    await rso.send(header)
    await rso.recv()
    await rso.recv()

    print('Sending auth header...')
    await rso.send(auth.decode())
    await rso.recv()

    print('Sending stream header...')
    await rso.send(header)
    await rso.recv()
    await rso.recv()

    print('Sending bind header...')
    await rso.send(bind.decode())
    await rso.recv()

    print('Sending ent header...')
    await rso.send(ent.decode())
    await rso.recv()

    print('Sending sesh header...')
    await rso.send(sesh.decode())
    await rso.recv()

    print('Starting continuous communication...')
    await rso.handle_communication()


if __name__ == '__main__':
    asyncio.run(main())
