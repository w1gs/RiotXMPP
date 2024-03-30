from src.Handlers.RiotXMPP import RiotXMMPClient
from src.Handlers.Auth import ValorantAuth
import asyncio


async def main():
    # Get authentication information of logged-in user
    auth = ValorantAuth(auth_type="local")
    creds = auth.tokens

    client = RiotXMMPClient(
        credentials=creds,
        region=auth.user_info["region"],
        chat_host=auth.user_info["chat_host"],
        chat_port=auth.user_info["chat_port"],
        puuid=auth.user_info["puuid"],
    )

    # Establish the connection
    await client.connect()

    # Initiate the authentication flow
    await client.start_auth_flow()

    # # Don't start processing messages if client is not connected
    if client.connected is True:
        # Start the main loop to start processing presences
        await client.process_presences(decode=True)


if __name__ == "__main__":
    # Run the loop using asyncio
    asyncio.run(main())
