"""Tests for Twitter/X API client.

Uses the `responses` library to mock HTTP requests.
"""

import pytest
import responses
import requests

from src.shell.twitter_client import (
    TwitterClient,
    TwitterResponse,
    TwitterCredentials,
    MediaUploadResponse,
    TWITTER_API_URL,
    TWITTER_MEDIA_UPLOAD_URL,
)


# Test credentials
TEST_CREDS = TwitterCredentials(
    api_key="test_api_key",
    api_secret="test_api_secret",
    access_token="test_access_token",
    access_token_secret="test_access_token_secret",
)


class TestTwitterClientSendTweet:
    """Tests for TwitterClient.send_tweet()."""

    @responses.activate
    def test_successful_tweet_returns_success(self):
        """Successful tweet returns TwitterResponse with success=True."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"data": {"id": "1234567890"}},
            status=201,
        )

        client = TwitterClient()
        result = client.send_tweet("Test tweet", TEST_CREDS)

        assert result.success is True
        assert result.status_code == 201
        assert result.tweet_id == "1234567890"
        assert result.error is None

    @responses.activate
    def test_sends_json_payload(self):
        """Tweet text is sent as JSON payload."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"data": {"id": "123"}},
            status=201,
        )

        client = TwitterClient()
        client.send_tweet("Hello world!", TEST_CREDS)

        request = responses.calls[0].request
        assert b'"text": "Hello world!"' in request.body

    @responses.activate
    def test_uses_oauth_authentication(self):
        """Request includes OAuth 1.0a authentication header."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"data": {"id": "123"}},
            status=201,
        )

        client = TwitterClient()
        client.send_tweet("Test", TEST_CREDS)

        request = responses.calls[0].request
        # OAuth 1.0a adds Authorization header
        assert "Authorization" in request.headers
        auth_header = request.headers["Authorization"]
        # Handle both string and bytes
        if isinstance(auth_header, bytes):
            auth_header = auth_header.decode("utf-8")
        assert "OAuth" in auth_header

    @responses.activate
    def test_rate_limited_returns_failure(self):
        """429 rate limit returns failure with error message."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"detail": "Too Many Requests"},
            status=429,
        )

        client = TwitterClient()
        result = client.send_tweet("Test", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 429
        assert "Rate limit" in result.error

    @responses.activate
    def test_auth_failure_returns_error(self):
        """401 auth failure returns descriptive error."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"detail": "Unauthorized"},
            status=401,
        )

        client = TwitterClient()
        result = client.send_tweet("Test", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 401
        assert "Authentication failed" in result.error

    @responses.activate
    def test_forbidden_returns_error_detail(self):
        """403 forbidden includes error detail from API."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"detail": "You are not permitted to perform this action"},
            status=403,
        )

        client = TwitterClient()
        result = client.send_tweet("Test", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 403
        assert "Forbidden" in result.error

    @responses.activate
    def test_server_error_returns_failure(self):
        """500 server error returns failure."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            body="Internal Server Error",
            status=500,
        )

        client = TwitterClient()
        result = client.send_tweet("Test", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 500

    @responses.activate
    def test_timeout_returns_failure(self):
        """Request timeout returns failure with timeout error."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            body=requests.Timeout("Connection timed out"),
        )

        client = TwitterClient(timeout=1)
        result = client.send_tweet("Test", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 0
        assert "timed out" in result.error.lower()

    @responses.activate
    def test_connection_error_returns_failure(self):
        """Connection error returns failure."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            body=requests.ConnectionError("Failed to connect"),
        )

        client = TwitterClient()
        result = client.send_tweet("Test", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 0
        assert result.error is not None


class TestTwitterClientSendTweets:
    """Tests for TwitterClient.send_tweets() batch method."""

    @responses.activate
    def test_sends_all_tweets(self):
        """All tweets are sent successfully."""
        for i in range(3):
            responses.add(
                responses.POST,
                TWITTER_API_URL,
                json={"data": {"id": str(i)}},
                status=201,
            )

        client = TwitterClient()
        texts = ["Tweet 1", "Tweet 2", "Tweet 3"]
        results = client.send_tweets(texts, TEST_CREDS, rate_limit_ms=0)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert len(responses.calls) == 3

    @responses.activate
    def test_continues_on_error_by_default(self):
        """Continues sending after error when stop_on_error=False."""
        responses.add(
            responses.POST, TWITTER_API_URL,
            json={"data": {"id": "1"}}, status=201
        )
        responses.add(
            responses.POST, TWITTER_API_URL,
            json={"detail": "Error"}, status=500
        )
        responses.add(
            responses.POST, TWITTER_API_URL,
            json={"data": {"id": "3"}}, status=201
        )

        client = TwitterClient()
        texts = ["Tweet 1", "Tweet 2", "Tweet 3"]
        results = client.send_tweets(texts, TEST_CREDS, rate_limit_ms=0)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True

    @responses.activate
    def test_stops_on_error_when_requested(self):
        """Stops sending after error when stop_on_error=True."""
        responses.add(
            responses.POST, TWITTER_API_URL,
            json={"data": {"id": "1"}}, status=201
        )
        responses.add(
            responses.POST, TWITTER_API_URL,
            json={"detail": "Error"}, status=500
        )
        responses.add(
            responses.POST, TWITTER_API_URL,
            json={"data": {"id": "3"}}, status=201
        )

        client = TwitterClient()
        texts = ["Tweet 1", "Tweet 2", "Tweet 3"]
        results = client.send_tweets(
            texts, TEST_CREDS, rate_limit_ms=0, stop_on_error=True
        )

        # Should stop after the error
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        # Third tweet should not have been sent
        assert len(responses.calls) == 2

    @responses.activate
    def test_empty_texts_returns_empty_list(self):
        """Empty texts list returns empty results."""
        client = TwitterClient()
        results = client.send_tweets([], TEST_CREDS)

        assert results == []
        assert len(responses.calls) == 0


class TestTwitterResponse:
    """Tests for TwitterResponse dataclass."""

    def test_success_response(self):
        """Successful response has correct fields."""
        response = TwitterResponse(
            success=True,
            status_code=201,
            tweet_id="1234567890",
        )

        assert response.success is True
        assert response.status_code == 201
        assert response.tweet_id == "1234567890"
        assert response.error is None

    def test_failure_response(self):
        """Failure response includes error message."""
        response = TwitterResponse(
            success=False,
            status_code=429,
            error="Rate limit exceeded",
        )

        assert response.success is False
        assert response.status_code == 429
        assert response.tweet_id is None
        assert response.error == "Rate limit exceeded"


class TestTwitterCredentials:
    """Tests for TwitterCredentials dataclass."""

    def test_credentials_fields(self):
        """Credentials dataclass has all required fields."""
        creds = TwitterCredentials(
            api_key="key",
            api_secret="secret",
            access_token="token",
            access_token_secret="token_secret",
        )

        assert creds.api_key == "key"
        assert creds.api_secret == "secret"
        assert creds.access_token == "token"
        assert creds.access_token_secret == "token_secret"


class TestTwitterClientUploadMedia:
    """Tests for TwitterClient.upload_media()."""

    @responses.activate
    def test_successful_upload_returns_media_id(self):
        """Successful upload returns MediaUploadResponse with media_id."""
        responses.add(
            responses.POST,
            TWITTER_MEDIA_UPLOAD_URL,
            json={"media_id": 1234567890, "media_id_string": "1234567890"},
            status=200,
        )

        client = TwitterClient()
        result = client.upload_media(b"PNG_IMAGE_DATA", TEST_CREDS)

        assert result.success is True
        assert result.status_code == 200
        assert result.media_id == "1234567890"
        assert result.error is None

    @responses.activate
    def test_uploads_base64_encoded_data(self):
        """Image data is base64 encoded in request."""
        responses.add(
            responses.POST,
            TWITTER_MEDIA_UPLOAD_URL,
            json={"media_id": 123, "media_id_string": "123"},
            status=200,
        )

        client = TwitterClient()
        client.upload_media(b"TEST", TEST_CREDS)

        request = responses.calls[0].request
        # "TEST" base64 encoded is "VEVTVA=="
        assert "VEVTVA==" in request.body

    @responses.activate
    def test_auth_failure_returns_error(self):
        """401 auth failure returns descriptive error."""
        responses.add(
            responses.POST,
            TWITTER_MEDIA_UPLOAD_URL,
            json={"errors": [{"message": "Unauthorized"}]},
            status=401,
        )

        client = TwitterClient()
        result = client.upload_media(b"PNG_DATA", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 401
        assert "Authentication failed" in result.error

    @responses.activate
    def test_file_too_large_returns_error(self):
        """413 file too large returns descriptive error."""
        responses.add(
            responses.POST,
            TWITTER_MEDIA_UPLOAD_URL,
            json={"errors": [{"message": "File too large"}]},
            status=413,
        )

        client = TwitterClient()
        result = client.upload_media(b"LARGE_DATA", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 413
        assert "too large" in result.error.lower()

    @responses.activate
    def test_timeout_returns_failure(self):
        """Request timeout returns failure."""
        responses.add(
            responses.POST,
            TWITTER_MEDIA_UPLOAD_URL,
            body=requests.Timeout("Connection timed out"),
        )

        client = TwitterClient(timeout=1)
        result = client.upload_media(b"PNG_DATA", TEST_CREDS)

        assert result.success is False
        assert result.status_code == 0
        assert "timed out" in result.error.lower()


class TestTwitterClientSendTweetWithMedia:
    """Tests for TwitterClient.send_tweet() with media attachments."""

    @responses.activate
    def test_tweet_with_media_ids(self):
        """Tweet with media IDs includes media in payload."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"data": {"id": "123"}},
            status=201,
        )

        client = TwitterClient()
        client.send_tweet("Test with image", TEST_CREDS, media_ids=["999"])

        request = responses.calls[0].request
        import json
        body = json.loads(request.body)
        assert "media" in body
        assert body["media"]["media_ids"] == ["999"]

    @responses.activate
    def test_tweet_without_media(self):
        """Tweet without media IDs doesn't include media field."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"data": {"id": "123"}},
            status=201,
        )

        client = TwitterClient()
        client.send_tweet("Test without image", TEST_CREDS)

        request = responses.calls[0].request
        import json
        body = json.loads(request.body)
        assert "media" not in body

    @responses.activate
    def test_tweet_with_multiple_media_ids(self):
        """Tweet can have multiple media IDs."""
        responses.add(
            responses.POST,
            TWITTER_API_URL,
            json={"data": {"id": "123"}},
            status=201,
        )

        client = TwitterClient()
        client.send_tweet("Multiple images", TEST_CREDS, media_ids=["111", "222"])

        request = responses.calls[0].request
        import json
        body = json.loads(request.body)
        assert body["media"]["media_ids"] == ["111", "222"]


class TestMediaUploadResponse:
    """Tests for MediaUploadResponse dataclass."""

    def test_success_response(self):
        """Successful response has media_id."""
        response = MediaUploadResponse(
            success=True,
            status_code=200,
            media_id="1234567890",
        )

        assert response.success is True
        assert response.status_code == 200
        assert response.media_id == "1234567890"
        assert response.error is None

    def test_failure_response(self):
        """Failure response includes error message."""
        response = MediaUploadResponse(
            success=False,
            status_code=413,
            error="File too large",
        )

        assert response.success is False
        assert response.status_code == 413
        assert response.media_id is None
        assert response.error == "File too large"
