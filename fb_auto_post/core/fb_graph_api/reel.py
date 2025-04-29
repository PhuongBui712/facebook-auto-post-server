import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from loguru import logger

from fb_auto_post.core.fb_graph_api.base import FacebookGraphAPIBase


class FacebookReelAPI(FacebookGraphAPIBase):
    """
    Class for interacting with the Facebook Reel API.
    
    Provides methods to post reels to Facebook Pages using the three-step process:
    1. Initialize upload session
    2. Upload the video file
    3. Publish the reel
    
    Inherits from FacebookGraphAPIBase to use the base request methods.
    """

    def __init__(self, api_version: str = FacebookGraphAPIBase.DEFAULT_API_VERSION):
        """
        Initializes the FacebookReelAPI with the specified API version.

        Args:
            api_version (str): The Facebook Graph API version to use.
                               Defaults to the version defined in FacebookGraphAPIBase.
        """
        super().__init__(api_version=api_version)

    async def post_reel(
        self,
        *,
        page_id: str,
        access_token: str,
        video_path: Union[str, Path],
        description: Optional[str] = None,
        share_to_feed: bool = False,
        thumbnail_path: Optional[Union[str, Path]] = None,
        check_upload_status: bool = True,
        status_check_interval: float = 5.0,
        max_status_checks: int = 12
    ) -> Dict[str, Any]:
        """
        Posts a reel to a Facebook Page using the three-step process defined by the Facebook Graph API.

        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            video_path (Union[str, Path]): Path to the video file for the reel.
            description (Optional[str]): Optional caption/description for the reel.
            video_state (str): The state of the video. Defaults to "PUBLISHED".
            share_to_feed (bool): Whether to share the reel to the page's feed. Defaults to False.
            thumbnail_path (Optional[Union[str, Path]]): Optional path to a thumbnail image.

        Returns:
            Dict[str, Any]: The response from the Facebook API.

        Raises:
            FileNotFoundError: If the video file is not found.
            Exception: For other API or request errors.
        """
        try:
            # Step 1: Initialize upload session
            session_data = await self._initialize_upload_session(page_id, access_token)
            video_id = session_data.get("video_id")
            upload_url = session_data.get("upload_url")
            
            if not video_id or not upload_url:
                raise ValueError(f"Failed to get valid video_id or upload_url: {session_data}")
            
            # Step 2: Upload the video file
            file_content = await self._read_file_async(video_path)
            file_size = len(file_content)
            
            headers = {
                "Authorization": f"OAuth {access_token}",
                "offset": "0",
                "file_size": str(file_size)
            }
            
            # Use direct upload request for the upload URL
            upload_result = await self._direct_upload_request(
                url=upload_url,
                headers=headers,
                content=file_content,
                timeout=90.0
            )

            if not upload_result.get("success"):
                logger.error(f"Video upload failed: {upload_result}")
                raise ValueError("Video upload was not successful")
            
            logger.success(f"Video file uploaded successfully")

            # # Optional: Check upload status before finalizing
            # if check_upload_status:
            #     await self._wait_for_video_ready(
            #         video_id=video_id,
            #         access_token=access_token,
            #         interval=status_check_interval,
            #         max_checks=max_status_checks
            #     )
            
            # Step 3: Publish the reel
            publish_response = await self._publish_reel(
                page_id=page_id,
                access_token=access_token,
                video_id=video_id,
                description=description
            )
            
            if not publish_response.get("success"):
                logger.error(f"Failed to finalize reel: {publish_response}")
                raise ValueError("Failed to finalize reel")
            
            logger.success(f"Reel posted successfully: {publish_response}")
            return {
                **publish_response,
                "video_id": video_id
            }
            
        except Exception as e:
            logger.error(f"Failed to post reel: {e}")
            raise

    async def _initialize_upload_session(self, page_id: str, access_token: str) -> Dict[str, Any]:
        """
        Initialize a video upload session (Step 1).
        
        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            
        Returns:
            Dict[str, Any]: The response containing video_id and upload_url.
        """
        endpoint = f"/{page_id}/video_reels"
        header = { "Content-Type": "application/json" }
        json_data = {
            "upload_phase": "start",
            "access_token": access_token
        }
        
        try:
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                url_type="base",
                json=json_data,
                headers=header
            )
        except Exception as e:
            logger.error(f"Failed to initialize upload session: {e}")
            raise

    async def _upload_video(
        self,
        upload_url: str,
        access_token: str,
        file_content: bytes,
        file_size: int,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Upload the video to Facebook (Step 2).
        
        Args:
            upload_url (str): The URL for uploading the video.
            access_token (str): The access token for the Page.
            file_content (bytes): The binary content of the video file.
            file_size (int): Size of the file in bytes.
            offset (int): Offset for resuming interrupted uploads. Defaults to 0.
            
        Returns:
            Dict[str, Any]: The response from the upload endpoint.
        """        
        headers = {
            "Authorization": f"OAuth {access_token}",
            "offset": str(offset),
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream"
        }
        
        try:
            return await self._direct_upload_request(
                url=upload_url,
                headers=headers,
                content=file_content
            )
        except Exception as e:
            logger.error(f"Failed to upload video: {e}")
            raise

    async def _wait_for_video_ready(
        self, 
        video_id: str, 
        access_token: str,
        interval: float = 5.0,
        max_checks: int = 12
    ) -> None:
        """
        Waits for a video to be ready for posting by checking its status periodically.

        Args:
            video_id (str): The ID of the video to check.
            access_token (str): The access token for authentication.
            interval (float): Seconds to wait between status checks. Defaults to 5.0.
            max_checks (int): Maximum number of status checks to perform. Defaults to 12.

        Raises:
            ValueError: If video processing fails or times out.
        """
        checks = 0
        while checks < max_checks:
            status = await self.get_reel_status(video_id, access_token)
            
            # if video_status == "ready":
            #     logger.debug(f"Video is ready for posting after {checks+1} checks")
            #     return
            # elif video_status == "error":
            #     error_msg = status.get("status", {}).get("processing_phase", {}).get("error", {}).get("message", "Unknown error")
            #     logger.error(f"Video processing error: {error_msg}")
            #     raise ValueError(f"Video processing error: {error_msg}")
            if status["uploading_phase"]["status"] == "complete":
                logger.debug(f"Video is ready for posting after {checks+1} checks")
                return
            elif status["uploading_phase"]["status"] == "expired":
                logger.error("Video upload expired")
                raise ValueError("Video upload expired")
            
            logger.debug(f"Video status check {checks+1}/{max_checks}: {status}")
            await asyncio.sleep(interval)
            checks += 1
        
        raise ValueError(f"Video processing timed out after {max_checks} checks")
    
    async def get_reel_status(
        self,
        video_id: str,
        access_token: str
    ) -> Dict[str, Any]:
        """
        Checks the status of a video upload.

        Args:
            video_id (str): The ID of the video to check.
            access_token (str): The access token for authentication.

        Returns:
            Dict[str, Any]: The status information from the API.
        """
        params = { "access_token": access_token, "fields": "status" }
        
        return (await self._make_request(
            method="GET",
            endpoint=f"/{video_id}",
            params=params
        )).get("status", {})

    async def _publish_reel(
        self,
        page_id: str,
        access_token: str,
        video_id: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Publish the uploaded video as a reel (Step 3).
        
        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            video_id (str): The ID of the uploaded video.
            description (Optional[str]): Caption for the reel.
            video_state (str): State of the video. Defaults to "PUBLISHED".
            
        Returns:
            Dict[str, Any]: The response from the API.
        """
        endpoint = f"/{page_id}/video_reels"
        params = {
            "access_token": access_token,
            "video_id": video_id,
            "upload_phase": "finish",
            "video_state": "PUBLISHED"
        }
        
        if description:
            params["description"] = description
            
        try:
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                params=params
            )
        except Exception as e:
            logger.error(f"Failed to publish reel: {e}")
            raise

    async def get_reel_info(
        self,
        *,
        reel_id: str,
        access_token: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Gets information about a specific reel.

        Args:
            reel_id (str): The ID of the reel.
            access_token (str): The access token for authentication.
            fields (Optional[List[str]]): Optional list of fields to return.
                                         If None, returns all available fields.

        Returns:
            Dict[str, Any]: The response from the Facebook API.

        Raises:
            Exception: For API or request errors.
        """
        if fields is None:
            fields = ["id", "permalink_url", "description", "updated_time", "status"]
            
        endpoint = f"/{reel_id}"
        params = {
            "access_token": access_token,
            "fields": ",".join(fields)
        }

        try:
            return await self._make_request(
                method="GET",
                endpoint=endpoint,
                params=params
            )
        except Exception as e:
            logger.error(f"Failed to get reel info: {e}")
            raise
            
    async def get_page_reels(
        self,
        *,
        page_id: str,
        access_token: str,
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gets a list of all reels published on a Facebook Page.
        
        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for authentication.
            since (Optional[str]): Optional start date filter (e.g., '2023-01-31' or timestamp).
            until (Optional[str]): Optional end date filter (must be after since).
            
        Returns:
            Dict[str, Any]: The response from the Facebook API containing reel data.
            
        Raises:
            Exception: For API or request errors.
        """
        endpoint = f"/{page_id}/video_reels"
        params = {
            "access_token": access_token
        }
        
        if since:
            params["since"] = since
        
        if until:
            params["until"] = until
            
        try:
            return await self._make_request(
                method="GET",
                endpoint=endpoint,
                params=params
            )
        except Exception as e:
            logger.error(f"Failed to get page reels: {e}")
            raise


async def main():
    import os

    api = FacebookReelAPI()
    response = await api.post_reel(
        page_id=os.getenv("DEV_FB_PAGE_ID"),
        access_token=os.getenv("DEV_FB_PAGE_ACCESS_TOKEN"),
        video_path="/Users/btp712/Downloads/test-n8n/bỏ liền thói xấu đó đi #hopecore.mp4"
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())