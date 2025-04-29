import os
import json

import pandas as pd
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from fb_auto_post.core.utils import get_project_root


class GoogleSheetsHelper:
    """Helper class to interact with Google Sheets API."""
    
    def __init__(self, credentials_file, token_file='token.json', scopes=None):
        """
        Initialize the Google Sheets API client.
        
        Args:
            credentials_file (str): Path to the credentials.json file from Google Cloud Console
            token_file (str): Path to save the token for authentication
            scopes (list): OAuth scopes for Google Sheets API
        """
        if scopes is None:
            self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        else:
            self.SCOPES = scopes
            
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API using token.json file."""
        creds = None
        
        # Load credentials from token.json file if exists
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_info(
                json.load(open(self.token_file)), self.SCOPES)
        
        # If no valid credentials, authenticate user
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        return build('sheets', 'v4', credentials=creds)
    
    def create_spreadsheet(self, title):
        """
        Create a new Google Sheet.
        
        Args:
            title (str): Title for the new spreadsheet
            
        Returns:
            str: ID of the created spreadsheet
        """
        spreadsheet = {
            'properties': {
                'title': title
            }
        }
        
        sheet = self.service.spreadsheets().create(body=spreadsheet, fields='spreadsheetId').execute()
        return sheet.get('spreadsheetId')
    
    def get_values(self, spreadsheet_id, range_name):
        """
        Get values from a Google Sheet.
        
        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            range_name (str): The range to retrieve (e.g., 'Sheet1!A1:C10')
            
        Returns:
            list: 2D list of values from the specified range
        """
        result = self.service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        return result.get('values', [])
    
    def update_values(self, spreadsheet_id, range_name, values, value_input_option='USER_ENTERED'):
        """
        Update values in a Google Sheet.
        
        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            range_name (str): The range to update (e.g., 'Sheet1!A1:C10')
            values (list): 2D list of values to update
            value_input_option (str): How input data should be interpreted
            
        Returns:
            dict: Response from the API
        """
        body = {
            'values': values
        }
        result = self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption=value_input_option, body=body).execute()
        return result
    
    def append_values(self, spreadsheet_id, range_name, values, value_input_option='USER_ENTERED'):
        """
        Append values to a Google Sheet.
        
        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            range_name (str): The range to append after (e.g., 'Sheet1!A:C')
            values (list): 2D list of values to append
            value_input_option (str): How input data should be interpreted
            
        Returns:
            dict: Response from the API
        """
        body = {
            'values': values
        }
        result = self.service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption=value_input_option, body=body).execute()
        return result
    
    def clear_values(self, spreadsheet_id, range_name):
        """
        Clear values from a Google Sheet.
        
        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            range_name (str): The range to clear (e.g., 'Sheet1!A1:C10')
            
        Returns:
            dict: Response from the API
        """
        result = self.service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        return result
    
    def get_sheet_as_dataframe(self, spreadsheet_id, range_name):
        """
        Get values from a Google Sheet as a pandas DataFrame.
        
        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            range_name (str): The range to retrieve (e.g., 'Sheet1!A1:C10')
            
        Returns:
            pandas.DataFrame: DataFrame containing the sheet data
        """
        values = self.get_values(spreadsheet_id, range_name)
        if not values:
            return pd.DataFrame()
            
        header = values[0]
        data = values[1:] if len(values) > 1 else []
        return pd.DataFrame(data, columns=header)
    
    def update_sheet_from_dataframe(self, spreadsheet_id, range_name, df, include_header=True):
        """
        Update a Google Sheet with data from a pandas DataFrame.
        
        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            range_name (str): The range to update (e.g., 'Sheet1!A1')
            df (pandas.DataFrame): DataFrame containing the data to update
            include_header (bool): Whether to include the DataFrame's column names as header
            
        Returns:
            dict: Response from the API
        """
        if include_header:
            values = [df.columns.tolist()] + df.values.tolist()
        else:
            values = df.values.tolist()
        
        return self.update_values(spreadsheet_id, range_name, values)
    
    def get_sheet_properties(self, spreadsheet_id):
        """
        Get properties of a Google Sheet.
        
        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            
        Returns:
            dict: Properties of the spreadsheet
        """
        result = self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        return result
    
    def add_sheet(self, spreadsheet_id, sheet_name):
        """
        Add a new sheet to an existing spreadsheet.
        
        Args:
            spreadsheet_id (str): The ID of the spreadsheet
            sheet_name (str): Name for the new sheet
            
        Returns:
            dict: Response from the API
        """
        request = {
            'addSheet': {
                'properties': {
                    'title': sheet_name
                }
            }
        }
        
        result = self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [request]}
        ).execute()
        return result


sheets_helper = GoogleSheetsHelper(
    credentials_file=os.path.join(get_project_root(), "credentials.json"),
    token_file=os.path.join(get_project_root(), "token.json")
)


if __name__ == '__main__':
    # Example: Use an existing spreadsheet (replace with your spreadsheet ID)
    # You can find the spreadsheet ID in the URL: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
    spreadsheet_id = os.getenv("PROD_SHEET_ID")
    
    # Example: Read data from the spreadsheet
    # data = sheets_helper.get_values(spreadsheet_id, os.getenv("PROD_PAGE_ACCESS_TOKEN_SHEET_NAME"))
    # print("Data from spreadsheet:")
    # for row in data:
    #     print(row)
    
    # Example: Get data as a pandas DataFrame
    df = sheets_helper.get_sheet_as_dataframe(spreadsheet_id, os.getenv("PROD_PAGE_ACCESS_TOKEN_SHEET_NAME"))
    print("\nData as DataFrame:")
    print(df)
    
    # Example: Update data
    # new_values = [
    #     ['Updated Name', 'Updated Age', 'Updated Email'],
    #     ['John Smith', 32, 'john.smith@example.com'],
    #     ['Sarah Johnson', 28, 'sarah@example.com']
    # ]
    # sheets_helper.update_values(spreadsheet_id, 'Sheet1!A1:C4', new_values)