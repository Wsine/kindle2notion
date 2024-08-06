from datetime import datetime
from typing import Dict, List, Tuple
from dateparser import parse
from dateutil.tz import tzlocal

from notion_client import Client
from requests import get

NO_COVER_IMG = "https://via.placeholder.com/150x200?text=No%20Cover"
ITALIC = "*"
BOLD = "**"

# TODO: Refactor this module

def export_to_notion(
    books: Dict,
    enable_highlight_date: bool,
    enable_book_cover: bool,
    notion_token: str,
    notion_table_id: str,
) -> None:
    print("Initiating transfer...\n")

    for title in books:
        print("Checking book: " + title)

        book = books[title]
        author = book["author"]
        highlights = book["highlights"]
        highlight_count = len(highlights)
        (
            aggregated_text_from_highlights,
            last_date,
        ) = _prepare_aggregated_text_for_one_book(highlights, enable_highlight_date)
        message = _add_book_to_notion(
            title,
            author,
            highlight_count,
            aggregated_text_from_highlights,
            last_date,
            notion_token,
            notion_table_id,
            enable_book_cover,
        )
        if message != "None to add":
            print("✓", message)

def _prepare_aggregated_text_for_one_book(
    highlights: List, enable_highlight_date: bool
) -> Tuple[str, str]:
    aggregated_text = ""
    for highlight in highlights:
        text = highlight[0]
        page = highlight[1]
        location = highlight[2]
        date = highlight[3]
        isNote = highlight[4]
        if isNote == True:
            aggregated_text += BOLD + "Note: " + BOLD

        aggregated_text += text + "\n("
        if page != "":
            aggregated_text += "Page: " + page + "  "
        if location != "":
            aggregated_text += "Location: " + location + "  "
        if enable_highlight_date and (date != ""):
            aggregated_text += "Date Added: " + date

        aggregated_text = aggregated_text.strip() + ")\n\n"
    last_date = date
    return aggregated_text, last_date


def _add_book_to_notion(
    title: str,
    author: str,
    highlight_count: int,
    aggregated_text: str,
    last_date: str,
    notion_token: str,
    notion_table_id: str,
    enable_book_cover: bool,
) -> str:
    notion_client = Client(auth=notion_token)
    notion_books_database = notion_client.databases.retrieve(notion_table_id)
    notion_books = notion_client.databases.query(notion_books_database['id']).get('results')

    title_exists = False
    if notion_books:
        for c_row in notion_books:
            book_info = c_row.get('properties')
            if title == book_info['Title']['title'][0]['plain_text']:
                title_exists = True
                row = c_row

                if row['properties']['Highlights']['number'] is None:
                    row['properties']['Highlights']['number'] = 0
                elif row['properties']['Highlights']['number'] == highlight_count:
                    return "None to add"


    title_and_author = title + " (" + str(author) + ")"
    print(title_and_author)
    print("-" * len(title_and_author))

    if not title_exists:
        new_page = {
            "Title": {"title": [{"text": {"content": title}}]},
            "Author": {
                "type": "rich_text",
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": author},
                    }
                ],
            },
            "Highlights": {"type": "number", "number": 0},
        }
        row = notion_client.pages.create(parent={"database_id": notion_table_id}, properties=new_page)


    parent_page = notion_client.pages.retrieve(row['id'])

    for all_blocks in notion_client.blocks.children.list(parent_page['id'])['results']:
        notion_client.blocks.delete(all_blocks['id'])

    # Split aggregated_text into paragraphs
    chunk_size = 1500
    chunks = [{'type': 'text', 'text': {'content': aggregated_text[i:i+chunk_size]}} for i in range(0, len(aggregated_text), chunk_size)]

    new_block = {
        'object': 'block',
        'type': 'paragraph',
        'paragraph': {
            'rich_text': chunks,
        }
    }
    notion_client.blocks.children.append(block_id=parent_page['id'], children=[new_block])

    diff_count = highlight_count - (row['properties']['Highlights']['number'] or 0)
    updated_info = {
        "Highlights": {"type": "number", "number": highlight_count},
        #  "Last Highlighted": {"type": "date", "date": {'start': parse(last_date).replace(tzinfo=tzlocal()).isoformat()}},
        "Last Synced": {"type": "date", "date": {'start': datetime.now(tzlocal()).isoformat()}},
    }
    notion_client.pages.update(page_id=row['id'], properties=updated_info)

    message = str(diff_count) + " notes / highlights added successfully\n"
    return message
