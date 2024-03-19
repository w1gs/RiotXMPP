from src.RiotXMPP import RiotXMMPClient
import asyncio


async def main():
    creds = {
        "rso_token": "xxxxxxxx",
        "entitlements_token": "xxxxxxxx",
        "pas_token": "xxxxxxxx",
    }

    region = "na1"
    chat_host = "na2.chat.si.riotgames.com"
    chat_port = 5223
    puuid = "xxxxxxxx"

    client = RiotXMMPClient(
        credentials=creds,
        region=region,
        chat_host=chat_host,
        chat_port=chat_port,
        puuid=puuid,
    )

    # Establish the connection
    await client.connect()

    # Initiate the authentication flow
    await client.start_auth_flow()

    try:
        # Start the main loop to start processing presences
        await client.process_messages()
    except asyncio.exceptions.IncompleteReadError:
        print("Shutting down...")


if __name__ == "__main__":
    # Run the loop using asyncio
    asyncio.run(main())
