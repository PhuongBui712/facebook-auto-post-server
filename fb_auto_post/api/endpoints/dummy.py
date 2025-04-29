import os
import asyncio
from typing import List, Optional

from loguru import logger
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, Query, Body, File, UploadFile, Form
from fastapi.responses import JSONResponse


load_dotenv


# Removed actual API imports as this is a dummy file
from fb_auto_post.core.fb_graph_api import (
    FacebookFeedAPI,
    FacebookStoryAPI,
    FacebookReelAPI,
    FacebookVideoAPI,
    get_orchestrated_page_tokens
)
from fb_auto_post.core.utils import force_remove
from fb_auto_post.api.protocols.facebook_post import *


# Initialize API Server metadata
app = FastAPI(
    title="Facebook content API (Dummy)", # Added (Dummy) to title
    description="API for handling posting Facebook content (Dummy endpoints)" # Added (Dummy) to description
)


# Removed API client initializations
# Initialize orchestration and posting handler
# feed_poster = FacebookFeedAPI()
# story_poster = FacebookStoryAPI()
# reel_poster = FacebookReelAPI()
# video_poster = FacebookVideoAPI()

# Removed orchestration logic
get_page_access_data = lambda: get_orchestrated_page_tokens(
    spreadsheet_id=os.getenv("DEV_SHEET_ID"),
    range_name=os.getenv("DEV_USER_ACCESS_TOKEN_SHEET_NAME")
)


# Initialize constants
# Removed retry constants as they are not needed for dummy endpoints
# MAX_RETRY = 3
# WAITING_TIME = 30
SLEEP_TIME = 0 * 60 # Define sleep time for dummy endpoints


@app.post("/feed", tags=["feed"], response_model=BasicResponse)
async def create_feed(request: PostFeedRequest):
    """
    DUMMY: Simulates creating a feed post. Always returns success.
    """
    print(f"Received DUMMY /feed request:")
    print(f"  Caption: {request.caption}")
    print(f"  Photos: {request.photo}")
    # Simulate a simple success response
    return BasicResponse(status="success", msg="Dummy success: Feed created.")
    # To simulate a failure:
    # return BasicResponse(status="error", msg="Dummy error: Failed to create feed.")
    # To simulate a warning (like some pages failed):
    # return BasicResponse(status="warning", msg="Dummy warning: Feed created, but failed on some pages.")


@app.post("/story/photo", tags=["story"], response_model=BasicResponse)
async def create_photo_story(request: PostPhotoStoryRequest):
    """
    DUMMY: Simulates creating a photo story. Always returns success.
    """
    print(f"Received DUMMY /story/photo request:")
    print(f"  Photo: {request.photo}")
    # Simulate a simple success response
    return BasicResponse(status="success", msg="Dummy success: Photo story created.")
    # To simulate a failure:
    # return BasicResponse(status="error", msg="Dummy error: Failed to create photo story.")


@app.post("/story/video", tags=["story"], response_model=PostContentResponse)
async def create_video_story(request: PostVideoStoryRequest):
    """
    DUMMY: Simulates creating a video story. Returns a mix of statuses.
    """
    print(f"Received DUMMY /story/video request:")
    print(f"  Video: {request.video}")

    await asyncio.sleep(SLEEP_TIME)

    # Simulate mixed results for multiple dummy pages
    dummy_responses = [
        PagePostContentResponse(status="success", content_type="story", page_names="Dummy Page 1 (Story)", page_url="https://facebook.com/dummy1", msg="Video posted successfully"),
        PagePostContentResponse(status="in_progress", content_type="story", page_names="Dummy Page 2 (Story)", page_url="https://facebook.com/dummy2", msg="Video is still processing"),
        PagePostContentResponse(status="error", content_type="story", page_names="Dummy Page 3 (Story)", page_url="https://facebook.com/dummy3", msg="Dummy error: Processing failed"),
        PagePostContentResponse(status="retry", content_type="story", page_names="Dummy Page 4 (Story)", page_url="https://facebook.com/dummy4", msg="Dummy: Will retry later"),
    ]
    return PostContentResponse(page_responses=dummy_responses)
    # To simulate a top-level error (e.g., bad request format before processing pages):
    # from fastapi import HTTPException
    # raise HTTPException(status_code=400, detail="Dummy bad request")


@app.post("/reel", tags=["reel"], response_model=PostContentResponse)
async def create_reel(request: PostReelRequest):
    """
    DUMMY: Simulates creating a reel. Returns a mix of statuses.
    """
    print(f"Received DUMMY /reel request:")
    print(f"  Caption: {request.caption}")
    print(f"  Video: {request.video}")
    print(f"  Share to Story: {request.share_to_story}")

    await asyncio.sleep(SLEEP_TIME)

    # Simulate mixed results for multiple dummy pages (similar to video story)
    dummy_responses = [
        PagePostContentResponse(status="success", content_type="reel", page_names="Dummy Page 1", page_url="https://facebook.com/dummyreel1", msg="Reel posted successfully"),
        PagePostContentResponse(status="in_progress", content_type="reel", page_names="Dummy Page 2", page_url="https://facebook.com/dummyreel2", msg="Reel is still processing"),
        PagePostContentResponse(status="error", content_type="reel", page_names="Dummy Page 3", page_url="https://facebook.com/dummyreel3", msg="Dummy error: Copyright issue"),
    ]


    if request.share_to_story:
        story_content_res: PostContentResponse = await create_video_story(PostVideoStoryRequest(video=request.video))
        dummy_responses.extend(story_content_res.page_responses)

    return PostContentResponse(page_responses=dummy_responses)


@app.post("/video", tags=["video"], response_model=BasicResponse)
async def create_video(request: PostVideoRequest):
    """
    DUMMY: Simulates creating a video post. Always returns success.
    """

    await asyncio.sleep(SLEEP_TIME)

    print(f"Received DUMMY /video request:")
    print(f"  Caption: {request.caption}")
    print(f"  Video: {request.video}")
    print(f"  Thumbnail: {request.thumbnail}")
    # Simulate a simple success response
    return BasicResponse(status="success", msg="Dummy success: Video posted.")
    # To simulate a failure:
    # return BasicResponse(status="error", msg="Dummy error: Failed to post video.")

if __name__ == "__main__":
    logger.info("Starting dummy Facebook content API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)