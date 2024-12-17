"""
Example of LinkedIn OAuth flow implementation.
"""

import asyncio
import os
from dotenv import load_dotenv
from oauth_service import LinkedInOAuth
from oauth_service.core import TokenManager

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize OAuth handler
    oauth = LinkedInOAuth(
        client_id=os.getenv("LINKEDIN_CLIENT_ID"),
        client_secret=os.getenv("LINKEDIN_CLIENT_SECRET"),
        callback_url=os.getenv("LINKEDIN_CALLBACK_URL")
    )
    
    # Get authorization URL
    auth_url = await oauth.get_authorization_url()
    print("\nAuthorization URL:")
    print(auth_url)
    
    # In a real app, user would be redirected to this URL
    # For this example, manually input the code
    code = input("\nEnter the authorization code: ")
    
    try:
        # Exchange code for tokens
        tokens = await oauth.get_access_token(code)
        print("\nTokens received:", tokens)
        
        # Store tokens
        token_manager = TokenManager()
        await token_manager.store_token("linkedin", "example_user", tokens)
        
        # Example: Create a LinkedIn post
        post_content = {
            "text": "Hello from OAuth Service! #ProfessionalUpdate",
            "visibility": "PUBLIC"
        }
        result = await oauth.create_post(tokens['access_token'], post_content)
        print("\nPost created:", result)
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
