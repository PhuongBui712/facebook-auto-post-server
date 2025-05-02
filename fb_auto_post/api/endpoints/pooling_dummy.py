import asyncio
import json
import os
from typing import Optional, List, Literal

import aiofiles
from loguru import logger
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, Field


# Define Response Statuses
ResponseStatus = Literal["success", "error", "accepted"]


class ProcessVideoStatus(BaseModel):
    status: Literal["success", "in_progress", "retry", "error"]
    msg: Optional[str] = None


class PostFeedRequest(BaseModel):
    caption: Optional[str] = ""
    photo: Optional[List[str]] = []
    task_id: str = Field(..., description="Unique identifier for the task")


class PostPhotoStoryRequest(BaseModel):
    photo: str
    task_id: str = Field(..., description="Unique identifier for the task")


class PostVideoStoryRequest(BaseModel):
    video: str
    task_id: str = Field(..., description="Unique identifier for the task")


class PostReelRequest(BaseModel):
    caption: Optional[str] = ""
    video: str
    share_to_story: bool = False
    task_id: str = Field(..., description="Unique identifier for the task")


class PostVideoRequest(BaseModel):
    caption: str = ""
    video: str
    thumbnail: str = ""
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
    page_responses: List[PagePostContentResponse]


# Ensure results directory exists
RESULT_DIR = "../results"
os.makedirs(RESULT_DIR, exist_ok=True)

# Initialize FastAPI app
app = FastAPI(
    title="Facebook Content API (Dummy)",
    description="API for handling posting Facebook content (No Callback)"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Simulate long-running tasks
SLEEP_TIME = 20 * 60  # seconds (for testing); set to real time in production


async def save_result(task_id: str, result_data: dict = None):
    """Save result as JSON in ../results/<task_id>.json. If result_data is None, creates an empty file."""
    filepath = os.path.join(RESULT_DIR, f"{task_id}.json")

    async with aiofiles.open(filepath, "w") as f:
        if result_data is None:
            await f.write("")  # Write empty file initially
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


@app.post("/feed", tags=["feed"], response_model=BasicResponse)
async def create_feed(request: PostFeedRequest):
    print(f"Received DUMMY /feed request:")
    print(f"  Caption: {request.caption}")
    print(f"  Photos: {request.photo}")

    # Create empty file immediately
    await save_result(request.task_id)

    async def process_task():
        await asyncio.sleep(SLEEP_TIME)  # Simulate processing
        result = {
            "status": "success",
            "msg": "Dummy success: Feed created."
        }
        await save_result(request.task_id, result)

    asyncio.create_task(process_task())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")


@app.post("/story/photo", tags=["story"], response_model=BasicResponse)
async def create_photo_story(request: PostPhotoStoryRequest):
    print(f"Received DUMMY /story/photo request:")
    print(f"  Photo: {request.photo}")

    await save_result(request.task_id)

    async def process_task():
        await asyncio.sleep(SLEEP_TIME)
        result = {
            "status": "success",
            "msg": "Dummy success: Photo story created."
        }
        await save_result(request.task_id, result)

    asyncio.create_task(process_task())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")


@app.post("/story/video", tags=["story"], response_model=BasicResponse)
async def create_video_story(request: PostVideoStoryRequest):
    print(f"Received DUMMY /story/video request:")
    print(f"  Video: {request.video}")

    await save_result(request.task_id)

    async def process_task():
        await asyncio.sleep(SLEEP_TIME)
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
        result = PostContentResponse(
            page_responses=dummy_responses
        ).dict()
        await save_result(request.task_id, result)

    asyncio.create_task(process_task())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")


@app.post("/reel", tags=["reel"], response_model=BasicResponse)
async def create_reel(request: PostReelRequest):
    print(f"Received DUMMY /reel request:")
    print(f"  Caption: {request.caption}")
    print(f"  Video: {request.video}")
    print(f"  Share to Story: {request.share_to_story}")

    await save_result(request.task_id)

    async def process_task():
        await asyncio.sleep(SLEEP_TIME)
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
            # Simulate calling create_video_story inline but without callback
            story_dummy_response = [
                PagePostContentResponse(
                    status="success",
                    content_type="story",
                    page_names="Dummy Page Story 1",
                    page_url="https://facebook.com/storydummy1",
                    msg="Posted to story"
                )
            ]
            dummy_responses.extend(story_dummy_response)

        result = PostContentResponse(
            page_responses=dummy_responses
        ).dict()
        await save_result(request.task_id, result)

    asyncio.create_task(process_task())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")


@app.post("/video", tags=["video"], response_model=BasicResponse)
async def create_video(request: PostVideoRequest):
    print(f"Received DUMMY /video request:")
    print(f"  Caption: {request.caption}")
    print(f"  Video: {request.video}")
    print(f"  Thumbnail: {request.thumbnail}")

    await save_result(request.task_id)

    async def process_task():
        await asyncio.sleep(SLEEP_TIME)
        result = {
            "status": "success",
            "msg": "Dummy success: Video posted."
        }
        await save_result(request.task_id, result)

    asyncio.create_task(process_task())
    return BasicResponse(status="accepted", msg="Task accepted. Awaiting processing.")