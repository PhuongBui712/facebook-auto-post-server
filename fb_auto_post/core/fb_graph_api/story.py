import json
import asyncio
from typing import Dict, Any, Optional, Union
from pathlib import Path

from loguru import logger

from fb_auto_post.core.fb_graph_api.base import FacebookGraphAPIBase


class FacebookStoryAPI(FacebookGraphAPIBase):
    """
    Class for interacting with the Facebook Story API.
    
    Provides methods to post stories to Facebook Pages.
    Inherits from FacebookGraphAPIBase to use the base request methods.
    """

    def __init__(self, api_version: str = FacebookGraphAPIBase.DEFAULT_API_VERSION):
        """
        Initializes the FacebookStoryAPI with the specified API version.

        Args:
            api_version (str): The Facebook Graph API version to use.
                               Defaults to the version defined in FacebookGraphAPIBase.
        """
        super().__init__(api_version=api_version)

    async def post_story_photo(
        self,
        *,
        page_id: str,
        access_token: str,
        photo_path: Union[str, Path],
        story_cta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Posts a photo story to a Facebook Page.
        
        This follows a two-step process:
        1. Upload the photo with published=false
        2. Post the photo as a story using the photo_id

        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            photo_path (Union[str, Path]): Path to the photo file.
            message (Optional[str]): Optional message to accompany the story.
            story_cta (Optional[Dict[str, Any]]): Optional call-to-action for the story
                Example: {'link': 'https://example.com', 'link_title': 'Visit Site'}

        Returns:
            Dict[str, Any]: The response from the Facebook API.

        Raises:
            FileNotFoundError: If the photo file is not found.
            Exception: For other API or request errors.
        """
        try:
            # Step 1: Upload the photo but don't publish it
            upload_params = {
                "access_token": access_token,
                "published": "false"
            }
                
            file_content = await self._read_file_async(photo_path)
            files = {"source": file_content}
            
            upload_response = await self._make_request(
                method="POST",
                endpoint=f"/{page_id}/photos",
                url_type="base",
                params=upload_params,
                files=files
            )
            
            if "id" not in upload_response:
                logger.error(f"Photo upload failed: {upload_response}")
                raise ValueError("Failed to get photo ID from upload response")
            
            photo_id = upload_response["id"]
            logger.debug(f"Photo uploaded successfully with ID: {photo_id}")
            
            # Step 2: Post the photo as a story
            story_params = { "access_token": access_token }
            story_json = { "photo_id": photo_id }
            
            # if story_cta:
            #     story_params["story_cta"] = json.dumps(story_cta)
            
            story_response = await self._make_request(
                method="POST",
                endpoint=f"/{page_id}/photo_stories",
                url_type="base",
                params=story_params,
                json=story_json
            )
            
            logger.debug(f"Story photo posted successfully: {story_response}")
            return story_response
        
        except Exception as e:
            logger.error(f"Failed to post story photo: {e}")
            raise

    async def post_story_video(
        self,
        *,
        page_id: str,
        access_token: str,
        video_path: Union[str, Path],
        story_cta: Optional[Dict[str, Any]] = None,
        check_upload_status: bool = True,
        status_check_interval: float = 5.0,
        max_status_checks: int = 12
    ) -> Dict[str, Any]:
        """
        Posts a video story to a Facebook Page.
        
        This follows a three-step process:
        1. Initialize upload session
        2. Upload the video file
        3. Finalize and post the video as a story

        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            video_path (Union[str, Path]): Path to the video file.
            story_cta (Optional[Dict[str, Any]]): Optional call-to-action for the story
                Example: {'link': 'https://example.com', 'link_title': 'Visit Site'}
            check_upload_status (bool): Whether to check the upload status before finalizing. Defaults to True.
            status_check_interval (float): Seconds to wait between status checks. Defaults to 5.0.
            max_status_checks (int): Maximum number of status checks to perform. Defaults to 12.

        Returns:
            Dict[str, Any]: The response from the Facebook API.

        Raises:
            FileNotFoundError: If the video file is not found.
            Exception: For other API or request errors.
        """
        try:
            # Step 1: Initialize upload session
            params = { "access_token": access_token }
            init_json = { "upload_phase": "start" }

            # if story_cta:
            #     params["story_cta"] = json.dumps(story_cta)
            
            init_response = await self._make_request(
                method="POST",
                endpoint=f"/{page_id}/video_stories",
                json=init_json,
                params=params,
            )
            
            if not all(key in init_response for key in ["video_id", "upload_url"]):
                logger.error(f"Failed to initialize video upload: {init_response}")
                raise ValueError("Missing video_id or upload_url in initialization response")
            
            video_id = init_response["video_id"]
            upload_url = init_response["upload_url"]
            
            logger.debug(f"Video upload initialized with ID: {video_id}")
            
            # Step 2: Upload the video file
            file_content = await self._read_file_async(video_path)
            file_size = len(file_content)
            
            headers = {
                "offset": "0",
                "file_size": str(file_size)
            }
            
            # Use direct upload request for the upload URL
            upload_result = await self._direct_upload_request(
                url=upload_url,
                params=params,
                headers=headers,
                content=file_content,
                timeout=90.0
            )
            
            if not upload_result.get("success"):
                logger.error(f"Video upload failed: {upload_result}")
                raise ValueError("Video upload was not successful")
            
            logger.success(f"Video file uploaded successfully")
            
            # Optional: Check upload status before finalizing
            # if check_upload_status:
            #     await self._wait_for_video_ready(
            #         video_id=video_id,
            #         access_token=access_token,
            #         interval=status_check_interval,
            #         max_checks=max_status_checks
            #     )
            
            # Step 3: Finalize and post the video as a story
            finalize_json = { "video_id": video_id, "upload_phase": "finish" }
            
            finish_response = await self._make_request(
                method="POST",
                endpoint=f"/{page_id}/video_stories",
                json=finalize_json,
                params=params,
            )
            
            if not finish_response.get("success"):
                logger.error(f"Failed to finalize video story: {finish_response}")
                raise ValueError("Failed to finalize video story")
            
            logger.success(f"Video story posted successfully: {finish_response}")
            return {
                **finish_response,
                "video_id": video_id
            }
            
        except Exception as e:
            logger.error(f"Failed to post story video: {e}")
            raise

    async def get_video_story_status(
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

    async def post_story_photo_from_url(
        self,
        *,
        page_id: str,
        access_token: str,
        photo_url: str,
        message: Optional[str] = None,
        story_cta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Posts a photo story to a Facebook Page using a photo URL.
        
        This follows a two-step process similar to post_story_photo but accepts a URL instead.

        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            photo_url (str): URL of the photo to post.
            message (Optional[str]): Optional message to accompany the story.
            story_cta (Optional[Dict[str, Any]]): Optional call-to-action for the story
                Example: {'link': 'https://example.com', 'link_title': 'Visit Site'}

        Returns:
            Dict[str, Any]: The response from the Facebook API.

        Raises:
            Exception: For API or request errors.
        """
        try:
            # Step 1: Upload the photo from URL but don't publish it
            upload_params = {
                "published": "false",  # Important: don't publish as regular post
                "url": photo_url
            }
            
            if message:
                upload_params["message"] = message
            
            upload_response = await self._make_request(
                method="POST",
                endpoint=f"/{page_id}/photos",
                url_type="base",
                params=upload_params,
                access_token=access_token
            )
            
            if "id" not in upload_response:
                logger.error(f"Photo upload failed: {upload_response}")
                raise ValueError("Failed to get photo ID from upload response")
            
            photo_id = upload_response["id"]
            logger.debug(f"Photo uploaded successfully with ID: {photo_id}")
            
            # Step 2: Post the photo as a story
            story_params = {
                "photo_id": photo_id
            }
            
            if story_cta:
                story_params["story_cta"] = json.dumps(story_cta)
            
            story_response = await self._make_request(
                method="POST",
                endpoint=f"/{page_id}/photo_stories",
                url_type="base",
                params=story_params,
                access_token=access_token
            )
            
            logger.debug(f"Story photo posted successfully: {story_response}")
            return story_response
        
        except Exception as e:
            logger.error(f"Failed to post story photo from URL: {e}")
            raise

    async def post_story_video_from_url(
        self,
        *,
        page_id: str,
        access_token: str,
        video_url: str,
        message: Optional[str] = None,
        story_cta: Optional[Dict[str, Any]] = None,
        check_upload_status: bool = True,
        status_check_interval: float = 5.0,
        max_status_checks: int = 12
    ) -> Dict[str, Any]:
        """
        Posts a video story to a Facebook Page using a video URL.
        
        This follows the three-step process for video stories but accepts a URL instead.

        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            video_url (str): URL of the video to post.
            message (Optional[str]): Optional message to accompany the story.
            story_cta (Optional[Dict[str, Any]]): Optional call-to-action for the story
                Example: {'link': 'https://example.com', 'link_title': 'Visit Site'}
            check_upload_status (bool): Whether to check the upload status before finalizing. Defaults to True.
            status_check_interval (float): Seconds to wait between status checks. Defaults to 5.0.
            max_status_checks (int): Maximum number of status checks to perform. Defaults to 12.

        Returns:
            Dict[str, Any]: The response from the Facebook API.

        Raises:
            Exception: For API or request errors.
        """
        try:
            # Step 1: Initialize upload session
            init_params = {
                "upload_phase": "start"
            }
            
            if message:
                init_params["message"] = message
                
            if story_cta:
                init_params["story_cta"] = json.dumps(story_cta)
            
            init_response = await self._make_request(
                method="POST",
                endpoint=f"/{page_id}/video_stories",
                url_type="video",
                params=init_params,
                access_token=access_token
            )
            
            if not all(key in init_response for key in ["video_id", "upload_url"]):
                logger.error(f"Failed to initialize video upload: {init_response}")
                raise ValueError("Missing video_id or upload_url in initialization response")
            
            video_id = init_response["video_id"]
            upload_url = init_response["upload_url"]
            
            logger.debug(f"Video upload initialized with ID: {video_id}")
            
            # Step 2: Upload the video from URL
            headers = {
                "file_url": video_url
            }
            
            # Use direct upload request for URL-based uploads
            upload_result = await self._direct_upload_request(
                url=upload_url,
                headers=headers,
                timeout=90.0
            )
            
            if not upload_result.get("success"):
                logger.error(f"Video URL upload failed: {upload_result}")
                raise ValueError("Video URL upload was not successful")
            
            logger.debug(f"Video URL uploaded successfully")
            
            # Optional: Check upload status before finalizing
            if check_upload_status:
                await self._wait_for_video_ready(
                    video_id=video_id,
                    access_token=access_token,
                    interval=status_check_interval,
                    max_checks=max_status_checks
                )
            
            # Step 3: Finalize and post the video as a story
            finalize_params = {
                "video_id": video_id,
                "upload_phase": "finish"
            }
            
            finish_response = await self._make_request(
                method="POST",
                endpoint=f"/{page_id}/video_stories",
                url_type="video",
                params=finalize_params,
                access_token=access_token
            )
            
            if not finish_response.get("success"):
                logger.error(f"Failed to finalize video story: {finish_response}")
                raise ValueError("Failed to finalize video story")
            
            logger.debug(f"Video story posted successfully: {finish_response}")
            return finish_response
            
        except Exception as e:
            logger.error(f"Failed to post story video from URL: {e}")
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
            status = await self.get_video_story_status(video_id, access_token)
            
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
    

async def main():
    import os

    api = FacebookStoryAPI()
    response = await api.post_story_photo(
        page_id=os.getenv("DEV_FB_PAGE_ID"),
        access_token=os.getenv("DEV_FB_PAGE_ACCESS_TOKEN"),
        photo_path="/Users/btp712/Downloads/Images/18x2 beyond the youthful day.webp"
    )


if __name__ == "__main__":
    asyncio.run(main())