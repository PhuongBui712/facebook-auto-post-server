from typing import Optional, List, Literal

from pydantic import BaseModel, AnyUrl, Field


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


class ReelResponse(BaseModel):
    status: ResponseStatus
    msg: str


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
