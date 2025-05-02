import os
import json
import asyncio
from typing import List, Dict, Tuple, Optional

import aiofiles
from loguru import logger
import uvicorn
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from fb_auto_post.core.fb_graph_api import (
    FacebookFeedAPI,
    FacebookStoryAPI,
    FacebookReelAPI,
    FacebookVideoAPI,
    get_orchestrated_page_tokens
)
from fb_auto_post.core.utils import force_remove
from fb_auto_post.api.protocols import *


# Initialize API Server metadata
app = FastAPI(
    title="Facebook content API",
    description="API for handling posting Facebook content"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Initialize orchestration and posting handler
feed_poster = FacebookFeedAPI()
story_poster = FacebookStoryAPI()
reel_poster = FacebookReelAPI()
video_poster = FacebookVideoAPI()

get_page_access_data = lambda: get_orchestrated_page_tokens(
    spreadsheet_id=os.getenv("DEV_SHEET_ID"),
    range_name=os.getenv("DEV_USER_ACCESS_TOKEN_SHEET_NAME")
)


# Initialize constants
MAX_RETRY = 3
WAITING_TIME = 30


# Ensure results directory exists
RESULT_DIR = "../results"
os.makedirs(RESULT_DIR, exist_ok=True)


async def save_result(task_id: str, result_data: dict = None):
    """Save result as JSON in ../results/<task_id>.json. If result_data is None, creates an empty file."""
    filepath = os.path.join(RESULT_DIR, f"{task_id}.json")

    async with aiofiles.open(filepath, "w") as f:
        if result_data is None:
            await f.write("")
        else:
            await f.write(json.dumps(result_data, indent=4))
    logger.info(f"Saved result for task {task_id}")


@app.get("/results/{task_id}", tags=["task"])
async def get_task_result(task_id: str):
    """Check task result with three possible states: not found, in progress, or done."""
    filepath = os.path.join(RESULT_DIR, f"{task_id}.json")

    if not os.path.exists(filepath):
        return Response(
            status_code=status.HTTP_404_NOT_FOUND,
            content=json.dumps({"status": "error", "msg": "Task not found"}),
            media_type="application/json"
        )

    try:
        async with aiofiles.open(filepath, "r") as f:
            content = await f.read()

        if not content.strip():  # Empty file
            return Response(
                status_code=status.HTTP_202_ACCEPTED,
                content=json.dumps({"status": "in_progress", "msg": "Task is still being processed."}),
                media_type="application/json"
            )
        else:  # File has content
            result = json.loads(content)
            return result

    except Exception as e:
        logger.error(f"Error reading result file: {e}")
        return Response(
            status_code=500,
            content=json.dumps({"status": "error", "msg": "Error reading result file."}),
            media_type="application/json"
        )


# Feed endpoint
@app.post("/feed", tags=["feed"], response_model=BasicResponse)
async def create_feed(request: PostFeedRequest):
    """
    Create a feed post with an optional caption and optional photos.
    - caption: Optional text for the feed
    - photos: Optional list of file paths to photos
    """
    # Create empty file immediately
    await save_result(request.task_id)
    try:
        async def process_task():
            # orchestrate page tokens to accounts
            page_access_data = await get_page_access_data()

            semaphore = asyncio.Semaphore(8)
            
            async def post_feed_safe(page):
                """Attempts to post a feed to a single page, returning success status or error."""
                async with semaphore:
                    try:
                        await feed_poster.post_feed(
                            page_id=page["page_id"],
                            access_token=page["access_token"],
                            message=request.caption,
                            photo_path=request.photo
                        )
                        logger.info(f"Successfully posted feed to page {page['page_id']}")
                        return page, True  # Indicate success
                    except Exception as e:
                        logger.error(f"Error posting to page {page['page_id']}: {e}")
                        return page, str(e)  # Indicate failure with exception message

            unpublished_pages = page_access_data.copy()
            running_time = 0
            failed_pages_details = {}  # Store the last error message for each failed page

            while unpublished_pages and running_time < MAX_RETRY:
                running_time += 1
                logger.info(f"Starting attempt {running_time} to post feed...")
                
                tasks = [post_feed_safe(page) for page in unpublished_pages]
                results = await asyncio.gather(*tasks)

                unpublished_pages = []  # Reset for next retry round

                for page, result in results:
                    if result is not True:
                        unpublished_pages.append(page)  # Add to retry list
                        failed_pages_details[page["page_id"]] = result  # Store error message
                        logger.warning(f"Page {page['page_id']} failed. Adding to retry list.")
                    else:
                        if page["page_id"] in failed_pages_details:
                            del failed_pages_details[page["page_id"]]  # Clear error message if now successful

                if unpublished_pages:
                    logger.info(f"Waiting {WAITING_TIME} seconds before retrying failed pages...")
                    await asyncio.sleep(WAITING_TIME)

            if not unpublished_pages:
                result = BasicResponse(
                    status="success",
                    msg="Successfully created feed on all pages"
                )
            else:
                error_message = f"Failed to post feed to the following pages after {MAX_RETRY} attempts:\n"
                for page_id, error in failed_pages_details.items():
                    error_message += f"- Page {page_id}: {error}\n"
                logger.error(error_message)
                result = BasicResponse(
                    status="warning",
                    msg=error_message
                )

            # delete file
            if request.photo:
                for file in request.photo:
                    force_remove(file)

            await save_result(request.task_id, result.model_dump())
            
        asyncio.create_task(process_task())
        return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")
    
    except Exception as e:
        logger.exception(f"An unexpected error occurred during feed creation: {e}")
        return BasicResponse(
            status="error",
            msg=f"An unexpected error occurred: {e}"
        )


# Story endpoints
@app.post("/story/photo", tags=["story"], response_model=BasicResponse)
async def create_photo_story(request: PostPhotoStoryRequest):
    """
    Create a story with a photo.
    - photo_path: File path to the photo
    """
    # Create empty file immediately
    await save_result(request.task_id)
    try:
        async def process_task():
            # orchestrate page tokens to accounts
            page_access_data = await get_page_access_data()

            # post photo story with retry mechanism
            semaphore = asyncio.Semaphore(8)

            async def post_story_photo_safe(page):
                """Attempts to post a photo story to a single page, returning success status or error."""
                async with semaphore:
                    try:
                        response = await story_poster.post_story_photo(
                            page_id=page["page_id"],
                            access_token=page["access_token"],
                            photo_path=request.photo
                        )
                        if response.get("success", False):
                            logger.info(f"Successfully attempted posting story to page {page['page_id']}")
                            return page, True  # Indicate success
                        else:
                            # If API call didn't raise exception but returned a falsy value, treat as failure
                            logger.error(f"API call for page {page['page_id']} returned falsy response: {response}")
                            return page, f"API returned falsy response: {response}"  # Indicate failure with response info
                    except Exception as e:
                        logger.error(f"Error posting to page {page['page_id']}: {e}")
                        return page, str(e)  # Indicate failure with exception message

            unpublished_pages = page_access_data.copy()
            running_time = 0
            failed_pages_details = {}

            while unpublished_pages and running_time < MAX_RETRY:
                logger.info(f"Attempt {running_time + 1} to post photo story to {len(unpublished_pages)} pages.")
                tasks = [post_story_photo_safe(page) for page in unpublished_pages]
                results = await asyncio.gather(*tasks)

                next_unpublished_pages = []
                attempt_failed_pages = []

                for page, result in results:
                    if result is True:
                        # Success for this page in this attempt
                        if page['page_id'] in failed_pages_details:
                            del failed_pages_details[page['page_id']]  # Remove if it was previously marked as failed
                    else:
                        # Failure for this page in this attempt
                        next_unpublished_pages.append(page)
                        attempt_failed_pages.append(page)
                        failed_pages_details[page['page_id']] = result  # Store the error message

                unpublished_pages = next_unpublished_pages

                if unpublished_pages and running_time < MAX_RETRY - 1:
                    # Wait before the next retry attempt, but only if there are pages to retry
                    logger.info(f"Waiting {WAITING_TIME} seconds before next retry...")
                    await asyncio.sleep(WAITING_TIME)

                running_time += 1

            if unpublished_pages:
                error_messages = [f"Page {page['page_id']}: {failed_pages_details.get(page['page_id'], 'Unknown error')}" for page in unpublished_pages]
                final_error_msg = "Failed to post story to the following pages after multiple retries:\n" + "\n".join(error_messages)
                logger.error(final_error_msg)
                result = BasicResponse(status="error", msg=final_error_msg)
            else:
                # All pages succeeded (eventually)
                logger.info("Photo story posted successfully to all pages.")
                result = BasicResponse(status="success", msg="Story posted successfully to all pages")

            # delete file
            force_remove(request.photo)

            await save_result(request.task_id, result.model_dump())
        
        asyncio.create_task(process_task())
        return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")
    
    except Exception as e:
        logger.exception(f"An unexpected error occurred during feed creation: {e}")
        return BasicResponse(
            status="error",
            msg=f"An unexpected error occurred: {e}"
        )


@app.post("/story/video", tags=["story"], response_model=BasicResponse)
async def create_video_story(request: PostVideoStoryRequest):
    """
    Create a story with a video.
    - video_path: File path to the video
    """
    # Create empty file immediately
    await save_result(request.task_id)
    try:
        async def process_task():
            page_responses: List[PagePostContentResponse] = []
            # orchestrate page tokens to accounts
            page_access_data = await get_page_access_data()

            # define posting tag
            semaphore = asyncio.Semaphore(6)
            async def post_story_video_safe(page):
                async with semaphore:
                    try:
                        response = await story_poster.post_story_video(
                            page_id=page["page_id"],
                            access_token=page["access_token"],
                            video_path=request.video  # Corrected parameter name
                        )
                        return page, response
                    except Exception as e:
                        logger.error(f"Error posting to page {page['page_id']}: {e}")
                        return page, {}

            # start posting process
            running_time = 0
            unpublished_pages: List[Dict[str, str]] = page_access_data.copy()
            success_pages: List[Dict[str, str]] = []
            in_progress_pages: List[Tuple[Dict[str, str], str]] = []
            error_pages: List[Tuple[Dict[str, str], str]] = []
            while unpublished_pages and running_time < MAX_RETRY:
                # post content
                publish_tasks = [post_story_video_safe(page) for page in unpublished_pages]
                results = await asyncio.gather(*publish_tasks)

                # sleep a while for server have time to complete
                await asyncio.sleep(WAITING_TIME)

                # define getting publishing status task
                async def get_publishing_status(page: Dict[str, str], video_id: Optional[str]) -> ProcessVideoStatus:
                    if not video_id:
                        return ProcessVideoStatus(status="retry")

                    retries = 3
                    for attempt in range(retries):
                        try:
                            status = await story_poster.get_video_story_status(
                                video_id=video_id,
                                access_token=page["access_token"]
                            )

                            # Publishing successfully
                            if status["publishing_phase"]["status"] == "complete":
                                return ProcessVideoStatus(status="success")
                            
                            elif status["processing_phase"]["status"] == "error":
                                # encounter "Creating error" while processing, retry
                                if (
                                    len(status["processing_phase"]["errors"]) == 1
                                    and status["processing_phase"]["errors"][0].get("code") == 1363008
                                ):
                                    return ProcessVideoStatus(status="retry")
                                
                                # encounter more than 1 error
                                else:
                                    error_messages = "\n".join(f"* {error['message']}" for error in status["processing_phase"]["errors"])
                                    return ProcessVideoStatus(status="error", msg=error_messages)

                            # publishing error, retry
                            if status["publishing_phase"]["status"] == "error":
                                return ProcessVideoStatus(status="retry")
                            
                            # The video itself is already corrupted.
                            elif (
                                "error" in status["processing_phase"]
                                and status["processing_phase"]["errors"][0]["code"] != 1363008
                            ):
                                error_messages = "\n".join(f"* {error['message']}" for error in status["processing_phase"]["errors"])
                                return ProcessVideoStatus(status="error", msg=error_messages)

                            # Not started or in progress
                            elif (
                                status["processing_phase"]["status"] in ("not_started", "in_progress") or
                                status["publishing_phase"]["status"] in ("not_started", "in_progress")
                            ):
                                return ProcessVideoStatus(status="in_progress")
                            
                            # Copyright error
                            elif "copyright_check_status" in status and status["copyright_check_status"]["status"] == "error":
                                return ProcessVideoStatus(status="error", msg="Copyright error detected")

                        except Exception as e:
                            logger.warning(f"Attempt {attempt + 1} failed for page {page['page_id']}: {e}")
                            if attempt == retries - 1:
                                logger.error(f"Max retries reached for page {page['page_id']}.  Failing.")
                                return ProcessVideoStatus(status="error", msg=str(e))
                            await asyncio.sleep((attempt) + 1 * 5)

                    return ProcessVideoStatus(status="retry")

                # conduct getting publishing status tasks
                data_to_get_status = in_progress_pages.copy() + [(page, result[1].get("video_id")) for page, result in zip(unpublished_pages, results)]
                status_results: List[ProcessVideoStatus] = await asyncio.gather(*[
                    get_publishing_status(page, video_id)
                    for page, video_id in data_to_get_status
                ])

                # check status
                unpublished_pages = []
                in_progress_pages = []
                for (page, video_id), process_status in zip(data_to_get_status, status_results):
                    process_status: ProcessVideoStatus
                    if process_status.status == "error":
                        error_pages.append((page, process_status.msg or "Can not publishing this video"))
                    elif process_status.status == "retry":
                        unpublished_pages.append(page)
                    elif process_status.status == "in_progress":
                        in_progress_pages.append((page, video_id))
                    else:
                        success_pages.append(page)
                
                # increase running count
                running_time += 1

            # synthesize results
            page_responses = [
                PagePostContentResponse(
                    status="success",
                    content_type="story",
                    page_names=page["page_name"],
                    page_url=f"https://facebook.com/{page['page_id']}",
                    msg="Video posted successfully"
                )
                for page in success_pages
            ]
            page_responses.extend(
                [
                    PagePostContentResponse(
                        status="in_progress",
                        content_type="story",
                        page_names=page["page_name"],
                        page_url=f"https://facebook.com/{page['page_id']}",
                        msg="Video is still processing"
                    )
                    for page, video_id in in_progress_pages
                ]
            )
            page_responses.extend(
                [
                    PagePostContentResponse(
                        status="retry",
                        content_type="story",
                        page_names=page["page_name"],
                        page_url=f"https://facebook.com/{page['page_id']}",
                        msg=f"Can not publish to page after {MAX_RETRY} attempts"
                    )
                    for page in unpublished_pages
                ]
            )
            page_responses.extend(
                [
                    PagePostContentResponse(
                        status="error",
                        content_type="story",
                        page_names=page["page_name"],
                        page_url=f"https://facebook.com/{page['page_id']}",
                        msg=msg
                    )
                    for page, msg in error_pages
                ]
            )

            # delete file
            force_remove(request.video)

            response = PostContentResponse(page_responses=page_responses)
            await save_result(request.task_id, response.model_dump())

        asyncio.create_task(process_task())
        return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")
    
    except Exception as e:
        logger.exception(f"An unexpected error occurred during video story creation: {e}")
        page_responses = [
            PagePostContentResponse(
                status="error",
                page_names="Unknown",
                page_url="https://facebook.com/",
                msg=f"An unexpected error occurred: {e}"
            )
        ]


# Reel endpoint
@app.post("/reel", tags=["reel"], response_model=BasicResponse)
async def create_reel(request: PostReelRequest):
    """
    Create a reel with an optional caption and optional video.
    - caption: Optional text for the reel
    - video_path: File path to the video
    """
    # Create empty file immediately
    await save_result(request.task_id)
    try:
        async def process_task():
            page_responses: List[PagePostContentResponse] = []
            # orchestrate page tokens to accounts
            page_access_data = await get_page_access_data()

            # define posting tag
            semaphore = asyncio.Semaphore(6)
            async def post_story_video_safe(page):
                async with semaphore:
                    try:
                        response = await reel_poster.post_reel(
                            page_id=page["page_id"],
                            access_token=page["access_token"],
                            video_path=request.video,
                            description=request.caption
                        )
                        return page, response
                    except Exception as e:
                        logger.error(f"Error posting to page {page['page_id']}: {e}")
                        return page, {}

            # start posting process
            running_time = 0
            unpublished_pages: List[Dict[str, str]] = page_access_data.copy()
            success_pages: List[Dict[str, str]] = []
            in_progress_pages: List[Tuple[Dict[str, str], str]] = []
            error_pages: List[Tuple[Dict[str, str], str]] = []
            while unpublished_pages and running_time < MAX_RETRY:
                # post content
                publish_tasks = [post_story_video_safe(page) for page in unpublished_pages]
                results = await asyncio.gather(*publish_tasks)

                # sleep a while for server have time to complete
                await asyncio.sleep(WAITING_TIME)

                # define getting publishing status task
                async def get_publishing_status(page: Dict[str, str], video_id: Optional[str]) -> ProcessVideoStatus:
                    if not video_id:
                        return ProcessVideoStatus(status="retry")

                    retries = 3
                    for attempt in range(retries):
                        try:
                            status = await reel_poster.get_reel_status(
                                video_id=video_id,
                                access_token=page["access_token"]
                            )

                            # Publishing successfully
                            if status["publishing_phase"]["status"] == "complete":
                                return ProcessVideoStatus(status="success")
                            
                            elif status["processing_phase"]["status"] == "error":
                                # encounter "Creating error" while processing, retry
                                if (
                                    len(status["processing_phase"]["errors"]) == 1
                                    and status["processing_phase"]["errors"][0].get("code") == 1363008
                                ):
                                    return ProcessVideoStatus(status="retry")
                                
                                # encounter more than 1 error
                                else:
                                    error_messages = "\n".join(f"* {error['message']}" for error in status["processing_phase"]["errors"])
                                    return ProcessVideoStatus(status="error", msg=error_messages)

                            # publishing error, retry
                            if status["publishing_phase"]["status"] == "error":
                                return ProcessVideoStatus(status="retry")
                            
                            # The video itself is already corrupted.
                            elif (
                                "error" in status["processing_phase"]
                                and status["processing_phase"]["errors"][0]["code"] != 1363008
                            ):
                                error_messages = "\n".join(f"* {error['message']}" for error in status["processing_phase"]["errors"])
                                return ProcessVideoStatus(status="error", msg=error_messages)

                            # Not started or in progress
                            elif (
                                status["processing_phase"]["status"] in ("not_started", "in_progress") or
                                status["publishing_phase"]["status"] in ("not_started", "in_progress")
                            ):
                                return ProcessVideoStatus(status="in_progress")
                            
                            # Copyright error
                            elif "copyright_check_status" in status and status["copyright_check_status"]["status"] == "error":
                                return ProcessVideoStatus(status="error", msg="Copyright error detected")

                        except Exception as e:
                            logger.warning(f"Attempt {attempt + 1} failed for page {page['page_id']}: {e}")
                            if attempt == retries - 1:
                                logger.error(f"Max retries reached for page {page['page_id']}.  Failing.")
                                return ProcessVideoStatus(status="error", msg=str(e))
                            await asyncio.sleep((attempt) + 1 * 5)

                    return ProcessVideoStatus(status="retry")

                # conduct getting publishing status tasks
                data_to_get_status = in_progress_pages.copy() + [(page, result[1].get("video_id")) for page, result in zip(unpublished_pages, results)]
                status_results: List[ProcessVideoStatus] = await asyncio.gather(*[
                    get_publishing_status(page, video_id)
                    for page, video_id in data_to_get_status
                ])

                # check status
                unpublished_pages = []
                in_progress_pages = []
                for (page, video_id), process_status in zip(data_to_get_status, status_results):
                    process_status: ProcessVideoStatus
                    if process_status.status == "error":
                        error_pages.append((page, process_status.msg or "Can not publishing this video"))
                    elif process_status.status == "retry":
                        unpublished_pages.append(page)
                    elif process_status.status == "in_progress":
                        in_progress_pages.append((page, video_id))
                    else:
                        success_pages.append(page)
                
                # increase running count
                running_time += 1

            page_responses = [
                PagePostContentResponse(
                    status="success",
                    content_type="reel",
                    page_names=page["page_name"],
                    page_url=f"https://facebook.com/{page['page_id']}",
                    msg="Video posted successfully"
                )
                for page in success_pages
            ]
            page_responses.extend(
                [
                    PagePostContentResponse(
                        status="in_progress",
                        content_type="reel",
                        page_names=page["page_name"],
                        page_url=f"https://facebook.com/{page['page_id']}",
                        msg="Video is still processing"
                    )
                    for page, video_id in in_progress_pages
                ]
            )
            page_responses.extend(
                [
                    PagePostContentResponse(
                        status="retry",
                        content_type="reel",
                        page_names=page["page_name"],
                        page_url=f"https://facebook.com/{page['page_id']}",
                        msg=f"Can not publish to page after {MAX_RETRY} attempts"
                    )
                    for page in unpublished_pages
                ]
            )
            page_responses.extend(
                [
                    PagePostContentResponse(
                        status="error",
                        content_type="reel",
                        page_names=page["page_name"],
                        page_url=f"https://facebook.com/{page['page_id']}",
                        msg=msg
                    )
                    for page, msg in error_pages
                ]
            )

            if request.share_to_story:
                post_video_story_res = await create_video_story(
                    request=PostVideoStoryRequest(
                        video=request.video,
                        task_id=request.task_id
                    )
                )
                page_responses.extend(post_video_story_res)

            # delete file
            force_remove(request.video)

            response = PostContentResponse(page_responses=page_responses)
            await save_result(request.task_id, response.model_dump())

        asyncio.create_task(process_task())
        return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred during video story creation: {e}")
        page_responses = [
            PagePostContentResponse(
                status="error",
                page_names="Unknown",
                page_url="https://facebook.com/",
                msg=f"An unexpected error occurred: {e}"
            )
        ]


# Video endpoint
@app.post("/video", tags=["video"], response_model=BasicResponse)
async def create_video(request: PostVideoRequest):
    """
    Create a video post with an optional caption and optional video.
    - caption: Optional text for the video post
    - video_path: File path to the video
    """
    # Create empty file immediately
    await save_result(request.task_id)
    try:
        async def process_task():
            # orchestrate page tokens to accounts
            page_access_data = await get_page_access_data()

            # post video with retry mechanism
            semaphore = asyncio.Semaphore(4)

            async def post_video_safe(page):
                """Attempts to post a video to a single page, returning success status or error."""
                async with semaphore:
                    try:
                        response = await video_poster.post_video(
                            page_id=page["page_id"],
                            access_token=page["access_token"],
                            video_path=request.video,
                            thumbnail_path=request.thumbnail,
                            description=request.caption,
                        )
                        if response.get("publish_video_status"):
                            return page, True
                        else:
                            return page, "Video publish or thumbnail failed"
                    except Exception as e:
                        logger.error(f"Error posting video to page {page['page_id']}: {e}")
                        return page, str(e)

            unpublished_pages = page_access_data.copy()
            running_time = 0
            failed_pages_details = {}

            while unpublished_pages and running_time < MAX_RETRY:
                logger.info(f"Attempt {running_time + 1} to post video to {len(unpublished_pages)} pages.")
                tasks = [post_video_safe(page) for page in unpublished_pages]
                results = await asyncio.gather(*tasks)

                next_unpublished_pages = []
                attempt_failed_pages = []

                for page, result in results:
                    if result is True:
                        # Success for this page in this attempt
                        if page['page_id'] in failed_pages_details:
                            del failed_pages_details[page['page_id']] # Remove if it was previously marked as failed
                    else:
                        # Failure for this page in this attempt
                        next_unpublished_pages.append(page)
                        attempt_failed_pages.append(page)
                        failed_pages_details[page['page_id']] = result # Store the error message

                unpublished_pages = next_unpublished_pages

                if unpublished_pages and running_time < MAX_RETRY - 1:
                    logger.info(f"Waiting {WAITING_TIME} seconds before next retry...")
                    await asyncio.sleep(WAITING_TIME)

                running_time += 1

            if unpublished_pages:
                error_messages = [
                    f"Page {page['page_id']}: {failed_pages_details.get(page['page_id'], 'Unknown error')}"
                    for page in unpublished_pages
                ]
                final_error_msg = "Failed to post video to the following pages after multiple retries:\n" + "\n".join(error_messages)
                logger.error(final_error_msg)
                result = BasicResponse(status="error", msg=final_error_msg)
            else:
                # All pages succeeded (eventually)
                logger.success("Video posted successfully to all pages.")
                result = BasicResponse(status="success", msg="Video posted successfully to all pages")

            await save_result(request.task_id, result.model_dump())

            # delete file
            force_remove(request.video)
            if request.thumbnail:
                force_remove(request.thumbnail)

        asyncio.create_task(process_task())
        return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")

    except Exception as e:
        logger.exception(f"An unexpected error occurred during video creation: {e}")
        return BasicResponse(
            status="error",
            msg=f"An unexpected error occurred: {e}"
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)