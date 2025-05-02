import uuid
import asyncio
from typing import Optional, List, Literal

import httpx
from loguru import logger
from fastapi import FastAPI
from pydantic import BaseModel, AnyUrl, HttpUrl, Field


# Define Response Statuses
ResponseStatus = Literal["success", "error", "accepted"]


class ProcessVideoStatus(BaseModel):
    status: Literal["success", "in_progress", "retry", "error"]
    msg: Optional[str] = None


class PostFeedRequest(BaseModel):
    caption: Optional[str] = ""
    photo: Optional[List[str]] = []
    callback_url: str
    task_id: str = Field(..., description="Unique identifier for the task")


class PostPhotoStoryRequest(BaseModel):
    photo: str
    callback_url: str
    task_id: str = Field(..., description="Unique identifier for the task")


class PostVideoStoryRequest(BaseModel):
    video: str
    callback_url: str
    task_id: str = Field(..., description="Unique identifier for the task")


class PostReelRequest(BaseModel):
    caption: Optional[str] = ""
    video: str
    share_to_story: bool = False
    callback_url: str
    task_id: str = Field(..., description="Unique identifier for the task")


class PostVideoRequest(BaseModel):
    caption: str = ""
    video: str
    thumbnail: str = ""
    callback_url: str
    task_id: str = Field(..., description="Unique identifier for the task")


class BasicResponse(BaseModel):
    status: ResponseStatus
    msg: str


class PagePostContentResponse(BaseModel):
    status: Literal["success", "in_progress", "error", "retry"]
    content_type: Literal["reel", "story"]
    page_names: str
    page_url: str
    msg: Optional[str]


class PostContentResponse(BaseModel):
    task_id: str = Field(..., description="Unique identifier for the task")
    page_responses: List[PagePostContentResponse]


# Initialize FastAPI app
app = FastAPI(
    title="Facebook content API (Dummy)",
    description="API for handling posting Facebook content (Dummy endpoints)"
)

# Simulate long-running tasks
SLEEP_TIME = 0.5 * 60  # 15 minutes


async def send_callback(callback_url: HttpUrl, response_data: dict):
    """
    Sends the response data to the provided callback URL.
    """
    try:
        async with httpx.AsyncClient() as client:
            await client.post(str(callback_url), json=response_data)
        logger.info(f"Callback sent to {callback_url}: {response_data}")
    except Exception as e:
        logger.error(f"Failed to send callback to {callback_url}: {e}")


@app.post("/feed", tags=["feed"], response_model=BasicResponse)
async def create_feed(request: PostFeedRequest):
    """
    DUMMY: Simulates creating a feed post and notifies the client via callback.
    """
    print(f"Received DUMMY /feed request:")
    print(f"  Caption: {request.caption}")
    print(f"  Photos: {request.photo}")

    async def process_and_notify():
        await asyncio.sleep(SLEEP_TIME)  # Simulate processing
        response_data = {
            "task_id": request.task_id,
            "status": "success",
            "msg": "Dummy success: Feed created."
        }
        if request.callback_url:
            await send_callback(request.callback_url, response_data)

    asyncio.create_task(process_and_notify())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")


@app.post("/story/photo", tags=["story"], response_model=BasicResponse)
async def create_photo_story(request: PostPhotoStoryRequest):
    """
    DUMMY: Simulates creating a photo story and notifies the client via callback.
    """
    print(f"Received DUMMY /story/photo request:")
    print(f"  Photo: {request.photo}")

    async def process_and_notify():
        await asyncio.sleep(SLEEP_TIME)  # Simulate processing
        response_data = {
            "task_id": request.task_id,
            "status": "success",
            "msg": "Dummy success: Photo story created."
        }
        if request.callback_url:
            await send_callback(request.callback_url, response_data)

    asyncio.create_task(process_and_notify())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")


@app.post("/story/video", tags=["story"], response_model=BasicResponse)
async def create_video_story(request: PostVideoStoryRequest):
    """
    DUMMY: Simulates creating a video story and notifies the client via callback.
    """
    print(f"Received DUMMY /story/video request:")
    print(f"  Video: {request.video}")

    async def process_and_notify():
        await asyncio.sleep(SLEEP_TIME)  # Simulate processing
        dummy_responses = [
            PagePostContentResponse(
                status="success",
                content_type="story",
                page_names="Dummy Page 1 (Story)",
                page_url="https://facebook.com/dummy1",
                msg="Video posted successfully",
            ),
            PagePostContentResponse(
                status="in_progress",
                content_type="story",
                page_names="Dummy Page 2 (Story)",
                page_url="https://facebook.com/dummy2",
                msg="Video is still processing",
            ),
        ]
        response_data = PostContentResponse(
            task_id=request.task_id,
            page_responses=dummy_responses
        ).dict()
        if request.callback_url:
            await send_callback(request.callback_url, response_data)

    asyncio.create_task(process_and_notify())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")


@app.post("/reel", tags=["reel"], response_model=BasicResponse)
async def create_reel(request: PostReelRequest):
    """
    DUMMY: Simulates creating a reel and notifies the client via callback.
    """
    print(f"Received DUMMY /reel request:")
    print(f"  Caption: {request.caption}")
    print(f"  Video: {request.video}")
    print(f"  Share to Story: {request.share_to_story}")

    async def process_and_notify():
        await asyncio.sleep(SLEEP_TIME)  # Simulate processing
        dummy_responses = [
            PagePostContentResponse(
                status="success",
                content_type="reel",
                page_names="Dummy Page 1",
                page_url="https://facebook.com/dummyreel1",
                msg="Reel posted successfully",
            ),
            PagePostContentResponse(
                status="in_progress",
                content_type="reel",
                page_names="Dummy Page 2",
                page_url="https://facebook.com/dummyreel2",
                msg="Reel is still processing",
            ),
        ]

        if request.share_to_story:
            story_content_res = await create_video_story(PostVideoStoryRequest(
                video=request.video,
                callback_url=None,
                task_id=request.task_id
            ))
            dummy_responses.extend(story_content_res.page_responses)

        response_data = PostContentResponse(
            task_id=request.task_id,
            page_responses=dummy_responses
        ).dict()
        if request.callback_url:
            await send_callback(request.callback_url, response_data)

    asyncio.create_task(process_and_notify())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")


@app.post("/video", tags=["video"], response_model=BasicResponse)
async def create_video(request: PostVideoRequest):
    """
    DUMMY: Simulates creating a video post and notifies the client via callback.
    """
    print(f"Received DUMMY /video request:")
    print(f"  Caption: {request.caption}")
    print(f"  Video: {request.video}")
    print(f"  Thumbnail: {request.thumbnail}")

    async def process_and_notify():
        await asyncio.sleep(SLEEP_TIME)  # Simulate processing
        response_data = {
            "task_id": request.task_id,
            "status": "success",
            "msg": "Dummy success: Video posted."
        }
        if request.callback_url:
            await send_callback(request.callback_url, response_data)

    asyncio.create_task(process_and_notify())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)