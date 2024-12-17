from setuptools import setup, find_packages

setup(
    name="oauth_service",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.1",
        "cryptography>=3.4.7",
        "fastapi>=0.68.1",
        "pydantic>=1.8.2",
        "python-dotenv>=0.19.0",
        "requests-oauthlib>=1.3.0",
        "SQLAlchemy>=1.4.23",
        "tweepy>=4.10.0",
        "uvicorn>=0.15.0",
    ],
    python_requires=">=3.8",
    author="Your Name",
    author_email="your.email@example.com",
    description="A comprehensive OAuth implementation supporting multiple platforms",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/oauth-service",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
