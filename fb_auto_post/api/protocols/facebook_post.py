from typing import Optional, List, Literal

from pydantic import BaseModel, AnyUrl


ResponseStatus = Literal["success", "error"]


class ProcessVideoStatus(BaseModel):
    status: Literal["success", "in_progress", "retry", "error"]
    msg: Optional[str] = None


class PostFeedRequest(BaseModel):
    caption: Optional[str] = ""
    photo: Optional[List[str]] = []


class PostPhotoStoryRequest(BaseModel):
    photo: str


class PostVideoStoryRequest(BaseModel):
    video: str


class PostReelRequest(BaseModel):
    caption: Optional[str] = ""
    video: str
    share_to_story: bool = False


class ReelResponse(BaseModel):
    status: ResponseStatus
    msg: str


class PostVideoRequest(BaseModel):
    caption: str = ""
    video: str
    thumbnail: str = ""


class BasicResponse(BaseModel):
    status: ResponseStatus
    msg: str


class PagePostContentResponse(BaseModel):
    status: Literal["success", "in_progress", "error", "retry"]
    content_type: Literal["reel", "story"]
    page_names: str
    page_url: AnyUrl
    msg: Optional[str]


class PostContentResponse(BaseModel):
    page_responses: List[PagePostContentResponse]
