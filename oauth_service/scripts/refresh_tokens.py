import asyncio
from ..services.token_refresh_service import TokenRefreshService
from ..utils.logger import get_logger

logger = get_logger(__name__)

async def main():
    service = TokenRefreshService()
    await service.check_and_refresh_tokens()

if __name__ == "__main__":
    asyncio.run(main()) 