"""
Example of Instagram OAuth flow implementation.
"""

import asyncio
import os
from dotenv import load_dotenv
from oauth_service import InstagramOAuth
from oauth_service.core import TokenManager

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize OAuth handler
    oauth = InstagramOAuth(
        client_id=os.getenv("INSTAGRAM_CLIENT_ID"),
        client_secret=os.getenv("INSTAGRAM_CLIENT_SECRET"),
        callback_url=os.getenv("INSTAGRAM_CALLBACK_URL")
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
        await token_manager.store_token("instagram", "example_user", tokens)
        
        # Get user profile
        profile = await oauth.get_user_profile(tokens['access_token'])
        print("\nUser profile:", profile)
        
        # Create an Instagram post with media
        # First, create a media container
        media_container = await oauth.create_media_container(
            tokens['access_token'],
            "https://example.com/image.jpg",
            "Hello from OAuth Service! #OAuth #API"
        )
        print("\nMedia container created:", media_container)
        
        # Then publish the post
        if media_container.get('container_id'):
            result = await oauth.publish_media(
                tokens['access_token'],
                media_container['container_id']
            )
            print("\nPost published:", result)
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
