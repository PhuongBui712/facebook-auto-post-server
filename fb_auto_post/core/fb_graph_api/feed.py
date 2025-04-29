import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

import aiofiles
from loguru import logger

from fb_auto_post.core.fb_graph_api.base import FacebookGraphAPIBase


class FacebookFeedAPI(FacebookGraphAPIBase):
    """
    Class for interacting with the Facebook Feed API.

    Inherits from FacebookGraphAPIBase to use the base request methods.
    """

    def __init__(self, api_version: str = FacebookGraphAPIBase.DEFAULT_API_VERSION):
        """
        Initializes the FacebookFeedAPI with the specified API version.

        Args:
            api_version (str): The Facebook Graph API version to use.
                               Defaults to the version defined in FacebookGraphAPIBase.
        """
        super().__init__(api_version=api_version)

    async def upload_photo(
        self,
        *,
        page_id: str,
        access_token: str,
        photo_path: Union[str, List[str], Path, List[Path]],
        published: bool = False,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads one or more photos to a Facebook Page without publishing them.

        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            photo_path (Union[str, List[str], Path, List[Path]]): Path(s) to the photo file(s).
            published (bool): Whether to publish the photo immediately. Defaults to False.
            caption (Optional[str]): Optional caption for the photo.

        Returns:
            Dict[str, Any]: The response from the Facebook API, containing the photo ID(s).

        Raises:
            FileNotFoundError: If a photo file is not found.
            Exception: For other API or request errors.
        """
        endpoint = f"/{page_id}/photos"
        params = {
            "access_token": access_token,
            "published": str(published).lower()
        }
        
        if caption:
            params["caption"] = caption

        # Normalize to list
        if isinstance(photo_path, (str, Path)):
            photo_paths = [photo_path]
        else:
            photo_paths = photo_path
            
        # Process photo paths in batches to avoid overwhelming
        BATCH_SIZE = 3
        all_responses = []
        
        # Process photos in batches
        for i in range(0, len(photo_paths), BATCH_SIZE):
            batch_paths = photo_paths[i:i+BATCH_SIZE]
            batch_tasks = []
            
            for path in batch_paths:
                task = self._upload_single_photo(endpoint, params, path)
                batch_tasks.append(task)
                
            # Wait for all tasks in this batch to complete
            batch_responses = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process responses, raising exceptions if needed
            for response in batch_responses:
                if isinstance(response, Exception):
                    logger.error(f"Error uploading photo: {response}")
                    raise response
                all_responses.append(response)
                
        return all_responses

    async def _upload_single_photo(self, endpoint: str, params: dict, photo_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Helper method to upload a single photo.
        
        Args:
            endpoint (str): API endpoint
            params (dict): Request parameters
            photo_path (Union[str, Path]): Path to the photo file
            
        Returns:
            Dict[str, Any]: API response
        """
        try:
            file_content = await self._read_file_async(photo_path)
            files = {"source": file_content}
            
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                params=params,
                files=files
            )
        except Exception as e:
            logger.error(f"Failed to upload photo {photo_path}: {e}")
            raise

    async def post_feed(
        self,
        *,
        page_id: str,
        access_token: str,
        message: str,
        link: Optional[str] = None,
        photo_path: Optional[Union[str, List[str], Path, List[Path]]] = None,
        max_concurrent: int = 3  # Control concurrency
    ) -> Dict[str, Any]:
        """
        Posts content to a Facebook Page feed.

        Supports text posts, link posts, single photo posts, and multiple photo posts.

        Args:
            page_id (str): The ID of the Facebook Page.
            access_token (str): The access token for the Page.
            message (str): The message content for the post.
            link (str, optional): An optional link to include in the post.
                                 Ignored as a structured link parameter if photo_path is provided.
            photo_path (Union[str, List[str], Path, List[Path]], optional): 
                        Optional path(s) to photo file(s) to upload.
            max_concurrent (int): Maximum number of concurrent operations. Defaults to 3.

        Returns:
            dict: The JSON response from the Facebook Graph API, typically containing the post ID.

        Raises:
            FileNotFoundError: If a specified photo file does not exist.
            Exception: For other API or request errors.
        """
        try:
            # Handle different post types
            if photo_path:
                return await self._post_with_photos(
                    page_id=page_id,
                    access_token=access_token,
                    message=message,
                    photo_path=photo_path,
                    max_concurrent=max_concurrent
                )
            elif link:
                # Simple link post
                endpoint = f"/{page_id}/feed"
                params = {
                    'access_token': access_token,
                    'message': message,
                    'link': link
                }
                return await self._make_request(
                    method="POST",
                    endpoint=endpoint,
                    params=params
                )
            else:
                # Simple text post
                endpoint = f"/{page_id}/feed"
                params = {
                    'access_token': access_token,
                    'message': message
                }
                return await self._make_request(
                    method="POST",
                    endpoint=endpoint,
                    params=params
                )
        except Exception as e:
            logger.exception(f"Error in post_feed: {e}")
            raise

    async def _post_with_photos(
        self,
        *,
        page_id: str,
        access_token: str,
        message: str,
        photo_path: Union[str, List[str], Path, List[Path]],
        max_concurrent: int = 3
    ) -> Dict[str, Any]:
        """
        Helper method to handle posts with photos.
        
        Args:
            page_id (str): The ID of the Facebook Page
            access_token (str): Access token for authentication
            message (str): Post message
            photo_path (Union[str, List[str], Path, List[Path]]): Photo path(s)
            max_concurrent (int): Maximum concurrent uploads
            
        Returns:
            Dict[str, Any]: API response
        """
        # Normalize to list
        if isinstance(photo_path, (str, Path)):
            # Single photo post - directly to photos endpoint with message
            endpoint = f"/{page_id}/photos"
            
            file_content = await self._read_file_async(photo_path)
            params = {
                'access_token': access_token,
                'message': message
            }
            files = {"source": file_content}
            
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                params=params,
                files=files
            )
        else:
            # Multiple photos - first upload unpublished, then post with attachments
            # Create a semaphore to limit concurrent uploads
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def upload_with_limit(path):
                async with semaphore:
                    return await self.upload_photo(
                        page_id=page_id,
                        access_token=access_token,
                        photo_path=path,
                        published=False
                    )
            
            # Upload all photos with concurrency limit
            upload_tasks = [upload_with_limit(path) for path in photo_path]
            upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            # Process results and check for errors
            attached_media = []
            for i, result in enumerate(upload_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to upload photo {i}: {result}")
                    raise result
                
                # Each result could be a list (from batch uploads) or single dict
                if isinstance(result, list):
                    for item in result:
                        attached_media.append({'media_fbid': item.get('id')})
                else:
                    attached_media.append({'media_fbid': result.get('id')})
            
            # Create the post with attached media
            endpoint = f"/{page_id}/feed"
            params = {
                'access_token': access_token,
                'message': message,
                'attached_media': json.dumps(attached_media)
            }
            
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                params=params
            )


async def main():
    """Example usage of the FacebookFeedAPI."""
    import os
    
    # Get credentials from environment variables
    page_id = os.getenv("DEV_FB_PAGE_ID")
    access_token = os.getenv("DEV_FB_PAGE_ACCESS_TOKEN")
    
    if not page_id or not access_token:
        print("Please set FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN environment variables")
        return
    
    poster = FacebookFeedAPI()
    
    # Example 1: Upload a single photo
    try:
        photo_result = await poster.upload_photo(
            page_id=page_id,
            access_token=access_token,
            photo_path="/Users/btp712/Downloads/thumbnails-2.jpg",
            caption="Test photo upload"
        )
        print(f"Photo upload result: {photo_result}")
    except Exception as e:
        print(f"Photo upload failed: {e}")
    
    # Example 2: Post a message with multiple photos
    try:
        post_result = await poster.post_feed(
            page_id=page_id,
            access_token=access_token,
            message="Testing multiple photo post",
            photo_path=["/Users/btp712/Downloads/Images/wallpaper.png", "/Users/btp712/Downloads/Images/wallpaper.webp"]
        )
        print(f"Post result: {post_result}")
    except Exception as e:
        print(f"Post failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())