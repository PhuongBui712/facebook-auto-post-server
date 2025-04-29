from pathlib import Path
from typing import Dict, Any, Optional, Union

import aiofiles
from loguru import logger

from fb_auto_post.core.fb_graph_api.base import FacebookGraphAPIBase


class FacebookVideoAPI(FacebookGraphAPIBase):
    """
    Class for uploading videos to Facebook Pages using the Graph API.
    
    Provides methods to upload large videos in chunks to Facebook Pages.
    Inherits from FacebookGraphAPIBase to use the base request methods.
    """

    def __init__(self, api_version: str = FacebookGraphAPIBase.DEFAULT_API_VERSION):
        """
        Initializes the FacebookVideoAPI with the specified API version.

        Args:
            api_version (str): The Facebook Graph API version to use.
                               Defaults to the version defined in FacebookGraphAPIBase.
        """
        super().__init__(api_version=api_version)

    async def post_video(
        self,
        *,
        page_id: str,
        access_token: str,
        video_path: Union[str, Path],
        thumbnail_path: Optional[Union[str, Path]] = None,
        description: Optional[str] = None,
        title: Optional[str] = None,
        chunk_size: int = 10 * 1048576,  # Default 10MB chunks
        log_progress: bool = True
    ) -> Optional[str]:
        """
        Upload a large video to Facebook in chunks
        
        Args:
            page_id (str): Facebook Page ID
            access_token (str): Page Access Token
            video_path (Union[str, Path]): Path to video file
            description (Optional[str]): Video description
            title (Optional[str]): Video title
            chunk_size (int): Size of each chunk in bytes (default 10MB)
            log_progress (bool): Whether to log progress (default True)
            
        Returns:
            Optional[str]: Video ID if successful, None if failed
        """
        # Check if file exists and get size
        video_path = Path(video_path)
        if not video_path.exists():
            logger.error("Video file not found")
            return None
            
        file_size = video_path.stat().st_size
        
        # Step 1: Start the upload session
        try:
            session_data = await self._start_upload_session(
                page_id=page_id,
                access_token=access_token,
                file_size=file_size
            )
            
            video_id = session_data.get('video_id')
            upload_session_id = session_data.get('upload_session_id')
            
            if not video_id or not upload_session_id:
                logger.error(f"Failed to get valid session data: {session_data}")
                return None
                
            logger.info(f"Upload session started. Video ID: {video_id}")
                
            # Step 2: Upload chunks
            start_offset = 0
            while start_offset < file_size:
                # Calculate chunk boundaries
                end_offset = min(start_offset + chunk_size - 1, file_size - 1)
                chunk_size_to_read = end_offset - start_offset + 1
                
                # Read the chunk using aiofiles
                async with aiofiles.open(video_path, 'rb') as video_file:
                    await video_file.seek(start_offset)
                    chunk = await video_file.read(chunk_size_to_read)
                
                # Upload the chunk
                transfer_result = await self._transfer_chunk(
                    page_id=page_id,
                    access_token=access_token,
                    upload_session_id=upload_session_id,
                    start_offset=start_offset,
                    chunk=chunk
                )
                    
                # Update start_offset from response
                start_offset = int(transfer_result.get('start_offset', start_offset))
                
                if log_progress:
                    progress = (start_offset / file_size) * 100
                    logger.info(f"Uploaded chunk: {start_offset}/{file_size} bytes ({progress:.2f}%)")
            
            # Step 3: Finish the upload
            finish_result = await self._finish_upload(
                page_id=page_id,
                access_token=access_token,
                upload_session_id=upload_session_id,
                description=description,
                title=title
            )
            
            if finish_result.get("success"):
                logger.success(f"Video uploaded successfully to page {page_id}! Video ID: {video_id}")
            
            # Step 4: Add thumbnail
            if thumbnail_path:
                thumbnail_result = await self.add_thumbnail(
                    video_id=video_id,
                    access_token=access_token,
                    thumbnail_path=thumbnail_path
                )
                if thumbnail_result.get("success"):
                    logger.success("Thumbnail uploaded successfully!")
                else:
                    logger.warning("Failed to upload thumbnail")

                return {
                    "publish_video_status": finish_result.get("success", "failed"),
                    "publish_thumbnail_status": thumbnail_result.get("success", "failed")
                }                
            else:
                return {
                    "publish_video_status": finish_result.get("success", "failed")
                }
            
        except Exception as e:
            logger.exception(f"Video upload failed: {e}")
            raise

    async def _start_upload_session(
        self,
        *,
        page_id: str,
        access_token: str,
        file_size: int
    ) -> Dict[str, Any]:
        """
        Start a video upload session
        
        Args:
            page_id (str): Facebook Page ID
            access_token (str): Page Access Token
            file_size (int): Size of video file in bytes
            
        Returns:
            Dict[str, Any]: Session data including video_id and upload_session_id
        """
        endpoint = f"/{page_id}/videos"
        params = {
            'upload_phase': 'start',
            'file_size': file_size,
            'access_token': access_token
        }
        
        try:
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                params=params,
                url_type="video"  # Use graph-video.facebook.com
            )
        except Exception as e:
            logger.error(f"Failed to start upload session: {e}")
            raise

    async def _transfer_chunk(
        self,
        *,
        page_id: str,
        access_token: str,
        upload_session_id: str,
        start_offset: int,
        chunk: bytes
    ) -> Dict[str, Any]:
        """
        Transfer a chunk of the video file
        
        Args:
            page_id (str): Facebook Page ID
            access_token (str): Page Access Token
            upload_session_id (str): Upload session ID
            start_offset (int): Starting byte offset for this chunk
            chunk (bytes): Binary chunk data
            
        Returns:
            Dict[str, Any]: Transfer result including new start_offset
        """
        endpoint = f"/{page_id}/videos"
        params = {
            'upload_phase': 'transfer',
            'start_offset': start_offset,
            'upload_session_id': upload_session_id,
            'access_token': access_token
        }
        
        files = {
            'video_file_chunk': ('chunk', chunk, 'video/mp4')
        }
        
        try:
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                params=params,
                files=files,
                url_type="video"  # Use graph-video.facebook.com
            )
        except Exception as e:
            logger.error(f"Chunk upload failed at offset {start_offset}: {e}")
            raise

    async def _finish_upload(
        self,
        *,
        page_id: str,
        access_token: str,
        upload_session_id: str,
        description: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Finish the video upload session
        
        Args:
            page_id (str): Facebook Page ID
            access_token (str): Page Access Token
            upload_session_id (str): Upload session ID
            description (Optional[str]): Video description
            title (Optional[str]): Video title
            
        Returns:
            Dict[str, Any]: Result of the finish operation
        """
        endpoint = f"/{page_id}/videos"
        params = {
            'upload_phase': 'finish',
            'upload_session_id': upload_session_id,
            'access_token': access_token
        }
        
        if description:
            params['description'] = description
            
        if title:
            params['title'] = title
        
        try:
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                params=params,
                url_type="video"  # Use graph-video.facebook.com
            )
        except Exception as e:
            logger.error(f"Failed to finish upload: {e}")
            raise

    async def add_thumbnail(
        self,
        video_id: str,
        thumbnail_path: Union[str, Path],
        access_token: str
    ):
        try:
            endpoint = f"/{video_id}/thumbnails"
            file_content = await self._read_file_async(thumbnail_path)
            files = {"source": file_content}
            params = {
                "is_preferred": "true",
                "access_token": access_token
            }
            
            return await self._make_request(
                method="POST",
                endpoint=endpoint,
                params=params,
                files=files
            )
        except Exception as e:
            logger.error(f"Failed to set thumbnail: {e}")
            raise


async def main():
    import os

    api = FacebookVideoAPI()
    response = await api.post_video(
        page_id=os.getenv("DEV_FB_PAGE_ID"),
        access_token=os.getenv("DEV_FB_PAGE_ACCESS_TOKEN"),
        video_path="/Users/btp712/Downloads/test-n8n/Mọi thứ đều là chất độc.mp4",
        description="Mọi thứ đều là chất độc\n#amazingscience",
        log_progress=True
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())