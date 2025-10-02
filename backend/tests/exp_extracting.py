import asyncio
import sys
from pathlib import Path
from pprint import pprint

# Add the server directory to the path so we can import from app
server_dir = Path(__file__).parent.parent
sys.path.insert(0, str(server_dir))

from app.services import extract_data


async def exp_full_extraction() -> None:
    """Run the extraction and dump the result for manual inspection."""
    url = "https://medium.com/physicsx/uncertainty-quantification-in-artificial-neural-networks-an-overview-1728f0a06c23"
    result = await extract_data(url)

    pprint(result)


if __name__ == "__main__":
    asyncio.run(exp_full_extraction())
