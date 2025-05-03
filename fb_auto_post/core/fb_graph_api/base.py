from pathlib import Path
from typing import Literal, List, Dict, Any, Optional, Union

import httpx
import aiofiles
from loguru import logger


FacebookGraphAPIUrl = Literal["base", "upload", "video"]


class FacebookGraphAPIBase:
    """
    Base class for interacting with the Facebook Graph API.

    Handles common functionalities like setting the API version and base URL.
    """

    DEFAULT_API_VERSION = "v22.0"
    BASE_URL = "https://graph.facebook.com"
    UPLOAD_URL = "https://rupload.facebook.com"
    VIDEO_URL = "https://graph-video.facebook.com"

    def __init__(self, api_version: str = DEFAULT_API_VERSION):
        """
        Initializes the base class with the specified API version.

        Args:
            api_version (str): The Facebook Graph API version to use (e.g., "v19.0").
                               Defaults to DEFAULT_API_VERSION.
        """
        if not api_version.startswith('v'):
            logger.warning(f"API version '{api_version}' does not start with 'v'. Prepending 'v'.")
            api_version = f"v{api_version}"

        self.api_version = api_version
        self.versioned_base_url = f"{self.BASE_URL}/{self.api_version}"
        self.versioned_upload_url = f"{self.UPLOAD_URL}/{self.api_version}"
        self.versioned_video_url = f"{self.VIDEO_URL}/{self.api_version}"
        logger.debug(f"Initialized FacebookGraphAPIBase with API version: {self.api_version}")

    async def get_accounts(
        self,
        user_access_token: str,
        limit: int = 500
    ):
        endpoint = "/me/accounts"
        try:
            response = await self._make_request(
                method="GET",
                endpoint=endpoint,
                params={ "limit": limit, "access_token": user_access_token }
            )
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise

    def _prepare_request_log(
        self,
        method: Literal["GET", "POST"],
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        log_params = {
            "method": method,
            "url": url,
            "params": params,
            "data": data,
            "files_count": len(files) if files else 0,
            "headers": headers,
            "json": json
        }
        log_message = ", ".join(f"{k}={v}" for k, v in log_params.items() if v)
        return log_message
    
    async def _make_request(
        self,
        method: Literal["GET", "POST"],
        endpoint: str,
        url_type: FacebookGraphAPIUrl = "base",
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Makes an asynchronous request to the Facebook Graph API.

        Args:
            method (str): HTTP method (e.g., "GET", "POST").
            endpoint (str): API endpoint path (e.g., "/me", "/{page_id}/feed").
            url_type (str): Type of URL to use ("base", "upload", or "video"). Defaults to "base".
            data (dict, optional): Request body data for POST/PUT requests. Defaults to None.
            files (dict, optional): Files to be sent with the request. Defaults to None.
            json (dict, optional): JSON data to be sent with the request. Defaults to None.
            headers (dict, optional): Request headers. Defaults to None.
            params (dict, optional): URL query parameters. Defaults to None.
            timeout (float, optional): Request timeout in seconds. Defaults to 30.0.

        Returns:
            dict: The JSON response from the API.

        Raises:
            httpx.HTTPStatusError: If the API returns an HTTP error status (4xx or 5xx).
            ValueError: If the API response contains an error message.
            Exception: For other network or unexpected errors.
        """
        # Select the appropriate base URL based on url_type
        if url_type == "base":
            base_url = self.versioned_base_url
        elif url_type == "upload":
            base_url = self.versioned_upload_url
        elif url_type == "video":
            base_url = self.versioned_video_url
        else:
            raise ValueError(f"Invalid URL type: {url_type}")
            
        url = f"{base_url}{endpoint}"

        # Create a client with specified timeout
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                log_message = self._prepare_request_log(
                    method,
                    url,
                    params,
                    data,
                    files,
                    json,
                    headers
                )
                logger.debug(f"Making {method} request to {url} with {log_message}")

                response = await client.request(
                    method,
                    url,
                    data=data,
                    files=files,
                    json=json,
                    params=params,
                    headers=headers
                )

                # Raise an exception for bad status codes (4xx or 5xx)
                response.raise_for_status()

                response_data = response.json()
                logger.info(f"Received successful response: {response_data}")

                # Check for Graph API specific errors which might not raise HTTPStatusError
                if isinstance(response_data, dict) and 'error' in response_data:
                    error_info = response_data['error']
                    error_message = (
                        f"Facebook API Error: "
                        f"Code={error_info.get('code')}, "
                        f"Type={error_info.get('type')}, "
                        f"Message={error_info.get('message')}"
                    )
                    logger.error(error_message)
                    raise ValueError(error_message)

                return response_data

            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                logger.error(f"HTTP Error calling Facebook API: {e.response.status_code} - {error_text}", exc_info=True)
                # Attempt to parse error details from response if possible
                try:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        error_info = error_data['error']
                        e.args = (f"{e.args[0]} - API Error: Code={error_info.get('code')}, Type={error_info.get('type')}, Message={error_info.get('message')}",)
                except Exception:
                    pass  # Ignore if response is not JSON or doesn't contain 'error'
                raise  # Re-raise the original exception with potentially more details
            except httpx.RequestError as e:
                logger.error(f"Network error connecting to Facebook API: {e}", exc_info=True)
                raise Exception(f"Network error: {e}") from e
            except Exception as e:
                logger.error(f"An unexpected error occurred during API call: {e}", exc_info=True)
                raise  # Re-raise the exception

    async def _direct_upload_request(
        self,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
        timeout: float = 90.0
    ) -> Dict[str, Any]:
        """
        Makes a direct upload request to the specified URL.
        
        This is used for special endpoints like video uploads that don't follow
        the standard Graph API pattern.

        Args:
            url (str): Full URL to send the request to
            headers (Dict[str, str]): Headers to send with the request
            content (Optional[bytes]): Binary content to upload
            timeout (float): Request timeout in seconds

        Returns:
            Dict[str, Any]: The JSON response

        Raises:
            Exception: If the request fails or returns an error
        """
        try:
            logger.debug(f"Making direct upload request to {url} with headers={headers}")
            async with httpx.AsyncClient(timeout=timeout) as client:
                if content:
                    response = await client.post(url, headers=headers, content=content, params=params)
                else:
                    response = await client.post(url, headers=headers, params=params)
                
                response.raise_for_status()
                response_data = response.json()
                
                logger.debug(f"Received upload response: {response_data}")
                return response_data
                
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            logger.error(f"HTTP error during direct upload: {e.response.status_code} - {error_text}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error during direct upload: {e}", exc_info=True)
            raise

    async def _read_file_async(self, file_path: Union[str, Path]) -> bytes:
        """
        Helper method to read a file asynchronously.

        Args:
            file_path (Union[str, Path]): Path to the file to read

        Returns:
            bytes: The file content as bytes

        Raises:
            FileNotFoundError: If the file does not exist
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
            
        async with aiofiles.open(file_path, 'rb') as f:
            return await f.read()
