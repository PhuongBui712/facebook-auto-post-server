import asyncio
from typing import List, Union, Optional

from fb_auto_post.core.fb_graph_api.base import FacebookGraphAPIBase
from fb_auto_post.core.ggsheet import sheets_helper


async def get_user_access_tokens(spreadsheet_id: str, range_name: str):
    sheet_data = sheets_helper.get_values(spreadsheet_id, range_name)
    user_access_tokens = [row[1] for row in sheet_data[1:]]

    return user_access_tokens


async def get_page_data(user_access_tokens: Union[str, List[str]]):
    if isinstance(user_access_tokens, str):
        user_access_tokens = [user_access_tokens]

    fb_api_handler = FacebookGraphAPIBase()

    async def get_page_token_task(user_token: str):
        pages = await fb_api_handler.get_accounts(user_token)
        return {
            d["id"]: {
                "access_token": d["access_token"],
                "page_name": d["name"],
            }
            for d in pages["data"]
        }

    tasks = [get_page_token_task(token) for token in user_access_tokens]
    return await asyncio.gather(*tasks)


async def get_orchestrated_page_tokens(spreadsheet_id: str, range_name: str):
    # Get users access tokens & associate pages access tokens
    user_access_tokens = await get_user_access_tokens(spreadsheet_id, range_name)
    page_data_per_user = await get_page_data(user_access_tokens)
    
    # Create a mapping of page_id -> list of users who have access to this page
    page_to_users = {}
    for user_idx, page_data in enumerate(page_data_per_user):
        for page_id, page_info in page_data.items():
            if page_id not in page_to_users:
                page_to_users[page_id] = []
            page_to_users[page_id].append({
                "user_idx": user_idx,
                "access_token": page_info["access_token"],
                "page_name": page_info["page_name"]
            })
    
    # Now orchestrate by selecting one token per page
    results = []
    num_accounts = len(user_access_tokens)
    acc_idx = 0
    
    for page_id, users_with_access in page_to_users.items():
        # Find a user that has access to this page
        available_users = users_with_access
        if not available_users:
            continue
        
        # Select a user based on the rotating index
        selected_idx = acc_idx % len(available_users)
        selected_user = available_users[selected_idx]
        
        results.append({
            "page_id": page_id,
            "access_token": selected_user["access_token"],
            "page_name": selected_user["page_name"]
        })
        
        # Increment index for next page
        acc_idx = (acc_idx + 1) % num_accounts
    
    return results


import os
import json

# # user_access_tokens = asyncio.run(get_user_access_tokens(
# #     spreadsheet_id=os.getenv("PROD_SHEET_ID"),
# #     range_name=os.getenv("PROD_USER_ACCESS_TOKEN_SHEET_NAME")
# # ))

# print(asyncio.run(
#     get_page_data("EAAQ2iE0QLo0BO1CBQvwe3BbMsp1tavEH9gR69oM2OVOVvkBEjOqc0bwJgjUpYYXBoiIFypFZBXxGOwijfqVlPwrWzSjtEvY2wk071BWiDvWSGNx87ArpCsPNxCZCPMZAUjkTmstBka11u20t6ZCBlsGiUT4MDOSu1tuF139SSYByRwQGNDWgthBo")
# ))


# orchestrated_page_tokens = asyncio.run(get_orchestrated_page_tokens(
#     spreadsheet_id=os.getenv("PROD_SHEET_ID"),
#     range_name=os.getenv("PROD_USER_ACCESS_TOKEN_SHEET_NAME")
# ))

# print(json.dumps(
#     orchestrated_page_tokens,
#     indent=4,
#     ensure_ascii=False
# ))