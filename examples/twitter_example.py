"""
Example of Twitter OAuth flow implementation.
"""

import asyncio
import os
from dotenv import load_dotenv
from oauth_service import TwitterOAuth
from oauth_service.core import TokenManager

async def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize OAuth handler
    oauth = TwitterOAuth(
        client_id=os.getenv("TWITTER_CLIENT_ID"),
        client_secret=os.getenv("TWITTER_CLIENT_SECRET"),
        callback_url=os.getenv("TWITTER_CALLBACK_URL")
    )
    
    # Get authorization URLs (both OAuth 1.0a and 2.0)
    auth_urls = await oauth.get_authorization_url()
    print("\nAuthorization URLs:")
    print(f"OAuth 1.0a: {auth_urls['oauth1_url']}")
    print(f"OAuth 2.0: {auth_urls['oauth2_url']}")
    
    # In a real app, user would be redirected to these URLs
    # For this example, manually input the codes
    oauth2_code = input("\nEnter OAuth 2.0 code: ")
    oauth1_verifier = input("Enter OAuth 1.0a verifier: ")
    
    # Exchange codes for tokens
    try:
        tokens = await oauth.get_access_token(
            oauth2_code=oauth2_code,
            oauth1_verifier=oauth1_verifier
        )
        print("\nTokens received:", tokens)
        
        # Store tokens
        token_manager = TokenManager()
        await token_manager.store_token("twitter", "example_user", tokens)
        
        # Example: Post a tweet
        tweet_content = {
            "text": "Hello from OAuth Service!",
            "media_urls": []
        }
        result = await oauth.create_tweet(tokens, tweet_content)
        print("\nTweet posted:", result)
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
