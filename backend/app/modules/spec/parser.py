import re
import uuid

from app.modules.spec.models import SpecBlock


def parse_spec_markdown(
    markdown: str,
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
    start_page: int,
    end_page: int,
) -> list[SpecBlock]:
    """Parse markdown text into a list of SpecBlock instances.

    Deterministic pipeline:
    - Headings detected by leading # characters (capped at 6)
    - List items detected by leading - / * or numbered patterns
    - Continuation lines (no marker) after a list item are merged into it
    - Everything else is a paragraph (consecutive lines grouped)
    - Parent assignment via heading stack
    """
    lines = markdown.split("\n")
    blocks: list[SpecBlock] = []
    # heading_stack: [(level, block_id), ...] sorted by level ascending
    heading_stack: list[tuple[int, uuid.UUID]] = []
    # list_stack: [(indent, block_id), ...] for nesting list items
    list_stack: list[tuple[int, uuid.UUID]] = []
    order = 0
    page_no = start_page

    # Regex patterns
    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")
    bullet_re = re.compile(r"^[\-\*]\s+")
    numbered_re = re.compile(r"^(\d+[.)]|[A-Za-z][.)])\s+")

    paragraph_lines: list[str] = []

    # List item accumulation (mirrors paragraph accumulation)
    list_item_lines: list[str] = []
    list_item_kind: str | None = None
    list_item_indent: int = 0

    def _flush_paragraph() -> None:
        nonlocal order
        if not paragraph_lines:
            return
        content = "\n".join(paragraph_lines)
        parent_id = heading_stack[-1][1] if heading_stack else None
        depth = heading_stack[-1][0] if heading_stack else None
        block = SpecBlock(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            document_id=document_id,
            page_no=page_no,
            parent_id=parent_id,
            order_in_page=order,
            style="paragraph",
            level=depth,
            list_kind=None,
            content=content,
        )
        blocks.append(block)
        order += 1
        paragraph_lines.clear()

    def _flush_list_item() -> None:
        nonlocal order
        if not list_item_lines:
            return
        content = "\n".join(list_item_lines)
        # Determine parent: check list_stack for a parent list item with less indent
        while list_stack and list_stack[-1][0] >= list_item_indent:
            list_stack.pop()
        if list_stack:
            # Sub-item: parent is the list item above in the stack
            parent_id = list_stack[-1][1]
            heading_level = heading_stack[-1][0] if heading_stack else 0
            depth = heading_level + len(list_stack) + 1
        else:
            # Top-level list item: parent is the heading
            parent_id = heading_stack[-1][1] if heading_stack else None
            heading_level = heading_stack[-1][0] if heading_stack else 0
            depth = heading_level + 1

        block_id = uuid.uuid4()
        block = SpecBlock(
            id=block_id,
            tenant_id=tenant_id,
            document_id=document_id,
            page_no=page_no,
            parent_id=parent_id,
            order_in_page=order,
            style="list_item",
            level=depth,
            list_kind=list_item_kind,
            content=content,
        )
        blocks.append(block)
        order += 1
        # Push this item onto the list stack so sub-items can reference it
        list_stack.append((list_item_indent, block_id))
        list_item_lines.clear()

    for line in lines:
        stripped = line.strip()

        # Skip blank lines (flush both accumulators)
        if not stripped:
            _flush_list_item()
            _flush_paragraph()
            continue

        # Measure indentation before stripping
        indent = len(line) - len(line.lstrip())

        # Heading detection (highest priority)
        heading_match = heading_re.match(stripped)
        if heading_match:
            _flush_list_item()
            _flush_paragraph()
            list_stack.clear()
            level = min(len(heading_match.group(1)), 6)
            # Pop stack entries with level >= N
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            # parent_id = nearest stack entry with level < N, else NULL
            parent_id = heading_stack[-1][1] if heading_stack else None
            block_id = uuid.uuid4()
            block = SpecBlock(
                id=block_id,
                tenant_id=tenant_id,
                document_id=document_id,
                page_no=page_no,
                parent_id=parent_id,
                order_in_page=order,
                style=f"Heading{level}",
                level=level,
                list_kind=None,
                content=stripped,
            )
            blocks.append(block)
            order += 1
            heading_stack.append((level, block_id))
            continue

        # List item detection — starts a NEW list item (flush any previous one)
        if bullet_re.match(stripped):
            _flush_list_item()
            _flush_paragraph()
            list_item_kind = "bullet"
            list_item_indent = indent
            list_item_lines.append(stripped)
            continue

        if numbered_re.match(stripped):
            _flush_list_item()
            _flush_paragraph()
            list_item_kind = "numbered"
            list_item_indent = indent
            list_item_lines.append(stripped)
            continue

        # If we're inside a list item, this is a continuation line — merge it
        if list_item_lines:
            list_item_lines.append(stripped)
            continue

        # Paragraph fallback — accumulate lines
        paragraph_lines.append(stripped)

    # Flush remaining accumulators
    _flush_list_item()
    _flush_paragraph()

    return blocks
