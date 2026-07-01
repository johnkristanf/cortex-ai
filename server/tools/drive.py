from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import io
from googleapiclient.http import MediaIoBaseDownload

@tool
def read_drive_file(filename: str) -> str:
    """Search for a file by name in Google Drive and read its contents. 
    Use this tool when the user asks to summarize or read a file from their Google Drive."""
    # The actual execution is handled by a custom node, so this function body 
    # might not be directly executed by the standard ToolNode, but we define it 
    # to provide the tool schema to the LLM.
    pass

def fetch_drive_file_content(filename: str, google_access_token: str) -> str:
    """Utility function to actually fetch the file content from Google Drive."""
    if not google_access_token:
        return "Error: No Google access token provided. Please sign in with Google."
        
    try:
        creds = Credentials(token=google_access_token)
        service = build('drive', 'v3', credentials=creds)
        
        # Search for the file
        query = f"name contains '{filename}'"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name, mimeType)').execute()
        items = results.get('files', [])
        
        if not items:
            return f"Error: No files found matching '{filename}'."
            
        # Take the first match
        file = items[0]
        file_id = file['id']
        mime_type = file['mimeType']
        
        content = ""
        # Google Workspace documents need to be exported
        if mime_type.startswith('application/vnd.google-apps.'):
            export_mime_type = 'text/plain'
            if mime_type == 'application/vnd.google-apps.document':
                export_mime_type = 'text/plain'
            else:
                return f"Error: Cannot export file type {mime_type} to text."
                
            request = service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            content = request.execute().decode('utf-8')
        else:
            # Standard files can be downloaded directly
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            content = fh.getvalue().decode('utf-8', errors='ignore')
            
        return content
        
    except HttpError as error:
        return f"A Google Drive API error occurred: {error}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"
