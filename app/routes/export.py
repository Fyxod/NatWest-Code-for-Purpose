from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
import markdown

from app.middlewares.auth import get_current_user_email
from core.database import db

router = APIRouter()


def _format_message_markdown(msg):
    role = "User" if msg["type"] == "user" else "Assistant"
    timestamp = msg.get("timestamp")
    formatted_time = ""
    if timestamp:
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted_time = timestamp
        else:
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    content = msg.get("content", "")

    # Header
    md = f"## {role} ({formatted_time})\n\n"
    md += f"{content}\n\n"

    # Sources for assistant messages
    if msg["type"] == "agent" and "sources" in msg:
        sources = msg["sources"]
        docs = sources.get("documents_used", [])
        if docs:
            md += "### Sources Used\n"
            for doc in docs:
                title = doc.get("title", "Untitled")
                page = doc.get("page_no", "?")
                md += f"- **{title}** (Page {page})\n"
            md += "\n"

    md += "---\n\n"
    return md


@router.get("/export/{thread_id}/markdown")
async def export_chat_markdown(
    thread_id: str, user_email: str = Depends(get_current_user_email)
):
    user = db.users.find_one({"email": user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    chats = thread.get("chats", [])
    if not chats:
        return Response(
            content="# No messages in this thread", media_type="text/markdown"
        )

    # Title from first message or thread ID
    title = f"Chat Export - {thread_id}"
    if chats and chats[0]["type"] == "user":
        title = f"Chat: {chats[0]['content'][:50]}..."

    # Build Markdown content
    md_content = f"# {title}\n"
    md_content += f"*Exported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

    for msg in chats:
        md_content += _format_message_markdown(msg)

    filename = f"chat_export_{thread_id}.md"

    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/{thread_id}/html")
async def export_chat_html(
    thread_id: str, user_email: str = Depends(get_current_user_email)
):
    user = db.users.find_one({"email": user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    thread = user.get("threads", {}).get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    chats = thread.get("chats", [])

    # Generate Markdown first
    title = f"Chat Export - {thread_id}"
    if chats and chats[0]["type"] == "user":
        title = f"Chat: {chats[0]['content'][:50]}..."

    md_content = f"# {title}\n"
    md_content += f"*Exported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"

    for msg in chats:
        md_content += _format_message_markdown(msg)

    # Convert to HTML
    html_body = markdown.markdown(
        md_content, extensions=["extra", "codehilite", "tables", "toc"]
    )

    # Wrap in template
    html_doc = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max_width: 800px; margin: 0 auto; padding: 20px; color: #333; }}
            h1 {{ border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }}
            h2 {{ color: #2c3e50; margin-top: 30px; border-bottom: 1px solid #eaeaea; padding-bottom: 5px; }}
            pre {{ background: #f6f8fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
            code {{ background: #f6f8fa; padding: 2px 5px; border-radius: 3px; font-family: Consolas, monospace; }}
            blockquote {{ border-left: 4px solid #dfe2e5; margin: 0; padding-left: 15px; color: #6a737d; }}
            table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
            th, td {{ border: 1px solid #dfe2e5; padding: 8px 12px; }}
            th {{ background: #f6f8fa; }}
            hr {{ border: 0; border-top: 1px solid #eaeaea; margin: 30px 0; }}
            .sources {{ font-size: 0.9em; color: #586069; }}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

    filename = f"chat_export_{thread_id}.html"

    return Response(
        content=html_doc,
        media_type="text/html",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
