from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
import os
from api.db.db_connection import get_db_connection
from api.utils.logger import logger

router = APIRouter()

class ValidateApiKeyRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    platform: str = Field(..., description="Platform name")
    api_key: str = Field(..., description="User's API key")

class ApiKeyResponse(BaseModel):
    api_key: str

@router.post("/validate", response_model=ApiKeyResponse)
async def validate_api_key(request: Request):
    """Validate user's API key."""
    # Validate the x-api-key header
    api_key = request.headers.get("x-api-key")
    if not api_key or api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        body = await request.json()
        try:
            data = ValidateApiKeyRequest(**body)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request body: {str(e)}")

        async with get_db_connection() as conn:
            query = """
                SELECT api_key
                FROM user_api_keys
                WHERE user_id = $1 AND platform = $2 AND api_key = $3
            """
            row = await conn.fetchrow(
                query,
                data.user_id,
                data.platform,
                data.api_key
            )

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"API key not found for user {data.user_id} on platform {data.platform}"
                )

            return {"api_key": row["api_key"]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating API key: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") 