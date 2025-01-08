def get_stored_api_key():
    try:
        # Add validation check
        api_key = retrieve_api_key_from_storage()
        if not api_key or len(api_key.strip()) == 0:
            logger.error("Retrieved API key is empty or invalid")
            return None
        return api_key
    except Exception as e:
        logger.error(f"Error retrieving API key: {str(e)}")
        return None 