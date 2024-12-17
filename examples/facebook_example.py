"""
Example of Facebook OAuth flow implementation.
"""

import asyncio
import os
from dotenv import load_dotenv
from oauth_service import FacebookOAuth
from oauth_service.core import TokenManager

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize OAuth handler
    oauth = FacebookOAuth(
        client_id=os.getenv("FACEBOOK_CLIENT_ID"),
        client_secret=os.getenv("FACEBOOK_CLIENT_SECRET"),
        callback_url=os.getenv("FACEBOOK_CALLBACK_URL")
    )
    
    # Get authorization URL with additional permissions
    auth_url = await oauth.get_authorization_url(
        extra_scopes=["pages_manage_posts", "pages_read_engagement"]
    )
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
        await token_manager.store_token("facebook", "example_user", tokens)
        
        # Get user's Facebook pages
        pages = await oauth.get_user_pages(tokens['access_token'])
        print("\nAvailable pages:", pages)
        
        if pages:
            # Create a post on the first page
            page = pages[0]
            post_content = {
                "text": "Hello from OAuth Service! 👋",
                "media_urls": []  # Add media URLs if needed
            }
            result = await oauth.create_page_post(
                page['access_token'],
                page['id'],
                post_content
            )
            print("\nPost created:", result)
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
