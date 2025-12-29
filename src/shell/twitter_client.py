"""Twitter/X API Client - Imperative Shell.

This module handles HTTP communication with the Twitter/X API v2.
All I/O is contained here; message formatting is in the core module.
"""

import base64
import logging
from dataclasses import dataclass

import requests
from requests_oauthlib import OAuth1


logger = logging.getLogger(__name__)


# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 10

# Twitter API v2 endpoint for posting tweets
TWITTER_API_URL = "https://api.twitter.com/2/tweets"

# Twitter API v1.1 endpoint for media upload
TWITTER_MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"


@dataclass
class TwitterResponse:
    """Response from Twitter API.

    Attributes:
        success: Whether the tweet was posted successfully
        status_code: HTTP status code
        tweet_id: ID of the created tweet if successful
        error: Error message if failed
    """
    success: bool
    status_code: int
    tweet_id: str | None = None
    error: str | None = None


@dataclass
class MediaUploadResponse:
    """Response from Twitter media upload API.

    Attributes:
        success: Whether the upload was successful
        status_code: HTTP status code
        media_id: Media ID string if successful (use this in tweets)
        error: Error message if failed
    """
    success: bool
    status_code: int
    media_id: str | None = None
    error: str | None = None


@dataclass
class TwitterCredentials:
    """Twitter API credentials for OAuth 1.0a authentication.

    Attributes:
        api_key: Twitter API Key (Consumer Key)
        api_secret: Twitter API Secret (Consumer Secret)
        access_token: User's Access Token
        access_token_secret: User's Access Token Secret
    """
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str


class TwitterClient:
    """Client for posting tweets via Twitter API v2.

    This is part of the imperative shell - it handles HTTP I/O.
    Uses OAuth 1.0a User Context for posting on behalf of a user.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize Twitter client.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    def _get_oauth(self, credentials: TwitterCredentials) -> OAuth1:
        """Create OAuth1 authentication object.

        Args:
            credentials: Twitter API credentials

        Returns:
            OAuth1 auth object for requests
        """
        return OAuth1(
            credentials.api_key,
            client_secret=credentials.api_secret,
            resource_owner_key=credentials.access_token,
            resource_owner_secret=credentials.access_token_secret,
        )

    def send_tweet(
        self,
        text: str,
        credentials: TwitterCredentials,
        media_ids: list[str] | None = None,
    ) -> TwitterResponse:
        """Post a tweet to Twitter/X.

        This method performs HTTP I/O.

        Args:
            text: Tweet text (max 280 characters)
            credentials: Twitter API credentials
            media_ids: Optional list of media IDs to attach

        Returns:
            TwitterResponse indicating success or failure
        """
        logger.info("Posting tweet to Twitter/X")

        # Validate tweet length
        if len(text) > 280:
            logger.warning("Tweet exceeds 280 characters, will be truncated by API")

        try:
            auth = self._get_oauth(credentials)

            # Build request payload
            payload: dict = {"text": text}
            if media_ids:
                payload["media"] = {"media_ids": media_ids}

            response = requests.post(
                TWITTER_API_URL,
                json=payload,
                auth=auth,
                timeout=self.timeout,
            )

            if response.status_code in (200, 201):
                data = response.json()
                tweet_id = data.get("data", {}).get("id")
                logger.info("Tweet posted successfully: %s", tweet_id)
                return TwitterResponse(
                    success=True,
                    status_code=response.status_code,
                    tweet_id=tweet_id,
                )
            elif response.status_code == 429:
                # Rate limit exceeded
                logger.warning("Twitter rate limit exceeded")
                return TwitterResponse(
                    success=False,
                    status_code=response.status_code,
                    error="Rate limit exceeded",
                )
            elif response.status_code == 401:
                logger.error("Twitter authentication failed")
                return TwitterResponse(
                    success=False,
                    status_code=response.status_code,
                    error="Authentication failed - check API credentials",
                )
            elif response.status_code == 403:
                error_detail = response.json().get("detail", response.text)
                logger.error("Twitter API forbidden: %s", error_detail)
                return TwitterResponse(
                    success=False,
                    status_code=response.status_code,
                    error=f"Forbidden: {error_detail}",
                )
            else:
                error_text = response.text
                logger.warning(
                    "Twitter API returned non-200: %d - %s",
                    response.status_code,
                    error_text,
                )
                return TwitterResponse(
                    success=False,
                    status_code=response.status_code,
                    error=error_text,
                )

        except requests.Timeout:
            logger.error("Twitter API request timed out")
            return TwitterResponse(
                success=False,
                status_code=0,
                error="Request timed out",
            )
        except requests.RequestException as e:
            logger.error("Twitter API request failed: %s", str(e))
            return TwitterResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    def upload_media(
        self,
        image_bytes: bytes,
        credentials: TwitterCredentials,
        media_type: str = "image/png",
    ) -> MediaUploadResponse:
        """Upload media to Twitter for use in tweets.

        Uses Twitter API v1.1 media upload endpoint.
        This method performs HTTP I/O.

        Args:
            image_bytes: Raw image data (PNG, JPEG, GIF, or WEBP)
            credentials: Twitter API credentials
            media_type: MIME type of the image (default: image/png)

        Returns:
            MediaUploadResponse with media_id or error
        """
        logger.info("Uploading media to Twitter (%d bytes)", len(image_bytes))

        try:
            auth = self._get_oauth(credentials)

            # Encode image as base64 for the upload
            media_data = base64.b64encode(image_bytes).decode("utf-8")

            response = requests.post(
                TWITTER_MEDIA_UPLOAD_URL,
                data={"media_data": media_data},
                auth=auth,
                timeout=self.timeout * 3,  # Longer timeout for uploads
            )

            if response.status_code in (200, 201):
                data = response.json()
                media_id = data.get("media_id_string")
                logger.info("Media uploaded successfully: %s", media_id)
                return MediaUploadResponse(
                    success=True,
                    status_code=response.status_code,
                    media_id=media_id,
                )
            elif response.status_code == 401:
                logger.error("Twitter media upload authentication failed")
                return MediaUploadResponse(
                    success=False,
                    status_code=response.status_code,
                    error="Authentication failed - check API credentials",
                )
            elif response.status_code == 413:
                logger.error("Media file too large for Twitter")
                return MediaUploadResponse(
                    success=False,
                    status_code=response.status_code,
                    error="Media file too large (max 5MB for images)",
                )
            else:
                error_text = response.text
                logger.warning(
                    "Twitter media upload returned non-200: %d - %s",
                    response.status_code,
                    error_text,
                )
                return MediaUploadResponse(
                    success=False,
                    status_code=response.status_code,
                    error=error_text,
                )

        except requests.Timeout:
            logger.error("Twitter media upload timed out")
            return MediaUploadResponse(
                success=False,
                status_code=0,
                error="Request timed out",
            )
        except requests.RequestException as e:
            logger.error("Twitter media upload failed: %s", str(e))
            return MediaUploadResponse(
                success=False,
                status_code=0,
                error=str(e),
            )

    def send_tweets(
        self,
        texts: list[str],
        credentials: TwitterCredentials,
        rate_limit_ms: int = 1000,
        stop_on_error: bool = False,
    ) -> list[TwitterResponse]:
        """Post multiple tweets with rate limiting.

        This is a deep method that handles:
        - Rate limiting between tweets
        - Optional early termination on error
        - Consistent response collection

        Args:
            texts: List of tweet texts
            credentials: Twitter API credentials
            rate_limit_ms: Delay between tweets in milliseconds (default: 1000)
            stop_on_error: If True, stop posting on first error

        Returns:
            List of responses for each tweet (may be shorter if stop_on_error)
        """
        import time

        responses = []

        for i, text in enumerate(texts):
            # Rate limit: wait before posting (except for first tweet)
            if i > 0 and rate_limit_ms > 0:
                time.sleep(rate_limit_ms / 1000.0)

            response = self.send_tweet(text, credentials)
            responses.append(response)

            # Early termination on error if requested
            if stop_on_error and not response.success:
                logger.warning(
                    "Stopping batch tweet after error on tweet %d of %d",
                    i + 1, len(texts),
                )
                break

        return responses
