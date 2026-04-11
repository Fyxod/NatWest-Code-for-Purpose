import asyncio
import json
import os
import time
from typing import List

import aiofiles

from app.socket_handler import sio
from core.embeddings.retriever import get_user_retriever
from core.llm.client import invoke_llm
from core.llm.outputs import (
    FlatNodeWithDescriptionOutput,
    GlobalMindMap,
    MindMapOutput,
    Node,
)
from core.models.document import Documents


# Constants
DESCRIPTION_PROCESSING_BATCH_SIZE = 4
PARALLEL_LLM_CALLS = 2


async def create_mind_map_global(parsed_data: Documents):
    """
    Generate a global mind map for the given parsed data.

    Invokes the LLM to create mind map nodes and descriptions.
    Retries up to 8 times on error. Emits progress updates via socket.

    Args:
        parsed_data: Documents object containing user data and thread information
    """
    await sio.emit(
        f"{parsed_data.user_id}/progress",
        {"message": "Started global mind map generation"},
    )

    incomplete_mind_map_dir = f"data/{parsed_data.user_id}/threads/{parsed_data.thread_id}/incomplete_mind_maps"
    os.makedirs(incomplete_mind_map_dir, exist_ok=True)

    prompt = build_mind_maps_node_prompt_global(parsed_data)
    total_start = time.time()
    max_retries = 15
    mind_map_emit_topic = (
        f"{parsed_data.user_id}/{parsed_data.thread_id}/mind_map/progress"
    )

    # Setup for continuous message broadcasting
    current_message = {"message": "Initializing mind map generation..."}
    broadcast_task = None
    stop_broadcast = asyncio.Event()

    async def broadcast_message():
        """Continuously broadcast the current message every 1 second."""
        while not stop_broadcast.is_set():
            await sio.emit(mind_map_emit_topic, current_message)
            try:
                await asyncio.wait_for(stop_broadcast.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def update_message(new_message: dict):
        """Update the current message and restart broadcasting."""
        nonlocal current_message, broadcast_task
        current_message = new_message
        if broadcast_task and not broadcast_task.done():
            stop_broadcast.set()
            await broadcast_task
            stop_broadcast.clear()
        broadcast_task = asyncio.create_task(broadcast_message())

    # Start initial broadcast
    broadcast_task = asyncio.create_task(broadcast_message())

    for attempt in range(max_retries):
        try:
            await update_message(
                {"message": f"Attempt {attempt + 1} of creating mind map"}
            )

            start = time.time()
            print(f"Invoking mind map node creation LLM (attempt {attempt + 1})")

            await update_message({"message": "Nodes creation in progress..."})

            response: MindMapOutput = await invoke_llm(
                response_schema=MindMapOutput,
                contents=prompt,
            )

            end = time.time()
            elapsed_time = end - start
            print(
                f"Mind map node titles generation completed in {elapsed_time:.2f} seconds"
            )

            await update_message(
                {
                    "message": f"Mind map node titles generation completed in {elapsed_time:.2f} seconds"
                }
            )

            # Prepare mind map data
            data_dict = response.model_dump()
            json_content = json.dumps(data_dict, indent=2, ensure_ascii=False)

            proper_mind_map_dir = (
                f"data/{parsed_data.user_id}/threads/{parsed_data.thread_id}/mind_maps"
            )
            os.makedirs(proper_mind_map_dir, exist_ok=True)

            # Initialize empty descriptions
            for node in data_dict["mind_map"]:
                node["description"] = ""

            mind_map_incomplete: GlobalMindMap = build_mindmap_global(
                data_dict["mind_map"], parsed_data.user_id, parsed_data.thread_id
            )
            mind_map_incomplete_dict = mind_map_incomplete.model_dump()

            # Save incomplete mind map files
            async with aiofiles.open(
                f"{proper_mind_map_dir}/{parsed_data.user_id}_{parsed_data.thread_id}_global_mind_map.json",
                "w",
                encoding="utf-8",
            ) as f:
                await f.write(
                    json.dumps(mind_map_incomplete_dict, indent=2, ensure_ascii=False)
                )

            async with aiofiles.open(
                f"{incomplete_mind_map_dir}/{parsed_data.user_id}_{parsed_data.thread_id}_global_mind_map.json",
                "w",
                encoding="utf-8",
            ) as f:
                await f.write(json_content)

            # Add node descriptions
            print("Starting to add node descriptions for global mind map...")
            await sio.emit(
                f"{parsed_data.user_id}/progress",
                {"message": "Global mind map nodes generation complete"},
            )
            await sio.emit(
                f"{parsed_data.user_id}/progress",
                {"message": "Creating node descriptions for GLOBAL mind map"},
            )
            await update_message(
                {"message": "Node descriptions creation in progress..."}
            )

            await add_node_descriptions_global(response, parsed_data, update_message)

            await sio.emit(
                f"{parsed_data.user_id}/progress",
                {"message": "Created node descriptions for GLOBAL mind map"},
            )

            total_end = time.time()
            total_elapsed = total_end - total_start
            print(
                f"Total time taken for mind map generation: {total_elapsed:.2f} seconds"
            )

            await update_message(
                {
                    "message": f"Total time taken for mind map generation: {total_elapsed:.2f} seconds"
                }
            )
            await asyncio.sleep(5)

            # Stop broadcasting and send final completion message
            stop_broadcast.set()
            if broadcast_task and not broadcast_task.done():
                await broadcast_task

            await sio.emit(
                mind_map_emit_topic,
                {"completed": True},
            )
            break

        except Exception as e:
            print(f"Error during mind map generation (attempt {attempt + 1}): {e}")
            await update_message(
                {
                    "message": f"Error during mind map generation (attempt {attempt + 1}): {e}"
                }
            )
            await asyncio.sleep(5)

            if attempt == max_retries - 1:
                print("Max retries reached. Mind map generation failed.")
                await update_message(
                    {"message": "Max retries reached. Mind map generation failed."}
                )
                await sio.emit(
                    f"{parsed_data.user_id}/progress",
                    {"message": "Failed to create GLOBAL mind map"},
                )
                await sio.emit(
                    f"{parsed_data.user_id}/{parsed_data.thread_id}/global_mind_map",
                    {"document_id": parsed_data.id, "status": False},
                )


async def add_node_descriptions_global(
    mind_map: MindMapOutput,
    parsed_data: Documents,
    update_message_callback=None,
):
    """
    Add descriptions to mind map nodes in batches.

    Processes node descriptions in batches of DESCRIPTION_PROCESSING_BATCH_SIZE nodes,
    with up to PARALLEL_LLM_CALLS batches processed in parallel.

    Args:
        mind_map: MindMapOutput containing nodes to process
        parsed_data: Documents object with user and thread information
        update_message_callback: Optional callback for progress updates
    """
    # Setup directories
    mind_map_dir = f"data/{parsed_data.user_id}/threads/{parsed_data.thread_id}/descriptions_mind_maps"
    os.makedirs(mind_map_dir, exist_ok=True)

    proper_mind_map_dir = (
        f"data/{parsed_data.user_id}/threads/{parsed_data.thread_id}/mind_maps"
    )
    os.makedirs(proper_mind_map_dir, exist_ok=True)

    # Prepare data and batches
    data = mind_map.model_dump()
    output_nodes = data["mind_map"]
    total_nodes = len(output_nodes)

    batches = [
        output_nodes[i : i + DESCRIPTION_PROCESSING_BATCH_SIZE]
        for i in range(0, total_nodes, DESCRIPTION_PROCESSING_BATCH_SIZE)
    ]

    doc_retriever = get_user_retriever(parsed_data.user_id, parsed_data.thread_id, k=8)

    async def update_mind_map(data):
        """Update and save the mind map to file."""
        try:
            # Ensure all nodes have description field
            for node in data["mind_map"]:
                if "description" not in node or not node["description"]:
                    node["description"] = ""

            mind_map_obj: GlobalMindMap = build_mindmap_global(
                data["mind_map"], parsed_data.user_id, parsed_data.thread_id
            )
            data_dict = mind_map_obj.model_dump()

            async with aiofiles.open(
                f"{proper_mind_map_dir}/{parsed_data.user_id}_{parsed_data.thread_id}_global_mind_map.json",
                "w",
                encoding="utf-8",
            ) as f:
                await f.write(json.dumps(data_dict, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"Error in update_mind_map: {e}")
            raise

    async def process_batch(batch_nodes, batch_idx):
        """Process a batch of nodes to generate descriptions."""
        if update_message_callback:
            await update_message_callback(
                {
                    "message": f"Creating descriptions for batch {batch_idx + 1} of {len(batches)}"
                }
            )

        # Retrieve relevant text for each node in batch
        batch_relevant_texts = []
        for node in batch_nodes:
            relevant_text = await doc_retriever.ainvoke(node["title"])
            relevant_str = "\n\n".join([doc.page_content for doc in relevant_text])
            batch_relevant_texts.append(relevant_str)

        # Attempt to generate descriptions with retries
        max_batch_retries = 10
        for batch_attempt in range(max_batch_retries):
            try:
                prompt = build_mind_maps_description_prompt(
                    batch_nodes, batch_relevant_texts
                )

                llm_res_bef = time.time()
                response: FlatNodeWithDescriptionOutput = await invoke_llm(
                    contents=prompt,
                    response_schema=FlatNodeWithDescriptionOutput,
                )
                llm_res_aft = time.time()

                print(
                    f"LLM response time: {llm_res_aft - llm_res_bef:.2f}s for mind map batch {batch_idx} (attempt {batch_attempt + 1})"
                )
                await sio.emit(
                    f"{parsed_data.user_id}/progress",
                    {
                        "message": f"Created descriptions for batch {batch_idx} (attempt {batch_attempt + 1})"
                    },
                )

                # Update node descriptions
                for i, node in enumerate(batch_nodes):
                    resp_node = (
                        response.mind_map[i] if i < len(response.mind_map) else None
                    )
                    if resp_node and node["id"] == resp_node.id:
                        node["description"] = resp_node.description
                        print(f"Updated description for node {node['id']}")
                    else:
                        print(f"Failed to update description for node {node['id']}")
                        if resp_node:
                            print(f"Expected ID: {node['id']}, but got: {resp_node.id}")

                await update_mind_map(data)
                break

            except Exception as e:
                print(
                    f"Error during description generation for batch {batch_idx} - GLOBAL MIND MAP (attempt {batch_attempt + 1}): {e}"
                )
                await asyncio.sleep(2)

                if batch_attempt == max_batch_retries - 1:
                    print(
                        f"Max retries reached for batch {batch_idx} - GLOBAL MIND MAP. Skipping batch."
                    )
                    await sio.emit(
                        f"{parsed_data.user_id}/progress",
                        {
                            "message": f"Failed to create descriptions for batch {batch_idx} - GLOBAL MIND MAP"
                        },
                    )

    # Process batches in parallel groups
    batch_count = len(batches)
    batch_idx = 0
    while batch_idx < batch_count:
        current_group = []
        for i in range(PARALLEL_LLM_CALLS):
            if batch_idx + i < batch_count:
                current_group.append(
                    process_batch(batches[batch_idx + i], batch_idx + i)
                )
        if current_group:
            await asyncio.gather(*current_group)
        batch_idx += PARALLEL_LLM_CALLS

    # Save final mind map with descriptions
    async with aiofiles.open(
        f"{mind_map_dir}/{parsed_data.user_id}_{parsed_data.thread_id}_global_mind_map.json",
        "w",
        encoding="utf-8",
    ) as f:
        await f.write(json.dumps(data, indent=2, ensure_ascii=False))

    print("Mind map built successfully")
    await sio.emit(
        f"{parsed_data.user_id}/progress",
        {"message": "GLOBAL Mind map built successfully"},
    )

    await update_mind_map(data)


def build_mind_maps_node_prompt_global(parsed_data: Documents) -> str:
    """
    Build the prompt for LLM to generate mind map nodes.

    Selects appropriate text (full text, summary, or truncated) for each document
    based on word count, then constructs a prompt for the LLM.

    Args:
        parsed_data: Documents object containing documents to process

    Returns:
        str: Formatted prompt for LLM
    """

    def word_count(text: str) -> int:
        return len(text.split())

    final_text = ""
    for document in parsed_data.documents:
        if hasattr(document, "full_text") and word_count(document.full_text) < 8000:
            print("Using full text for mind map creation")
            text = document.full_text
        elif hasattr(document, "summary") and document.summary:
            print("Using summary for mind map creation")
            text = document.summary
        else:
            print("Using truncated text for mind map creation")
            words = document.full_text.split()[:8000]
            text = " ".join(words)
        final_text += f"\nTitle - {document.title}\n\n{text}\n\n"

    return f"""
Respond with a valid JSON of nodes (max_limit: 100).
You are to create a mind map node structure from the provided text. 
The output must be in JSON with the following rules:
- Each node must contain: id, title, and parent_id.
- id: a unique identifier for the node.
- title: the text label for the node.
- parent_id: the id of the parent node, or null if it is a root node.
- Preserve the logical hierarchy of concepts by linking nodes through parent_id.

Guidelines:
- Try to balance breadth and depth: some branches should expand into 4-6 levels where natural.
- Break down complex topics into smaller sub-concepts, examples, or details, instead of grouping them all as direct children of the root.
- Cover each document really well in detail.
- Do not exceed the max limit of 100 nodes.
- Keep only 1 root node if possible.

Text: {final_text}
"""


def build_mind_maps_description_prompt(
    nodes: List[dict], relevant_texts: List[str]
) -> str:
    """
    Build the prompt for LLM to generate node descriptions.

    Args:
        nodes: List of node dictionaries with 'id' and 'title'
        relevant_texts: List of relevant source texts for each node

    Returns:
        str: Formatted prompt for LLM
    """
    prompt = """
You are to write clear, concise, and informative descriptions of 40-50 words for each of the following mind map nodes.
For each node, the description should explain what the concept means. It should be useful to the user, no blabbering about anything else.
Take reference and help from the provided source text for each node but don't reference them in the description itself.
"""
    for i, node in enumerate(nodes):
        prompt += f"\nNode {i+1}:\n  Node id: {node['id']}\n  Node title: {node['title']}\n  Source text: {relevant_texts[i]}\n"
    return prompt


def build_mindmap_global(
    flat_nodes: List[dict],
    user_id: str,
    thread_id: str,
) -> GlobalMindMap:
    """
    Build a hierarchical mind map structure from flat node list.

    Converts flat node dictionaries into a tree structure by linking
    children to their parents via parent_id.

    Args:
        flat_nodes: List of node dictionaries with 'id', 'parent_id', etc.
        user_id: User identifier
        thread_id: Thread identifier

    Returns:
        GlobalMindMap: Hierarchical mind map with root nodes
    """
    # Convert dicts into Node objects
    nodes = {n["id"]: Node(**n, children=[]) for n in flat_nodes}
    roots = []

    # Assign children to parents
    for node in nodes.values():
        if node.parent_id:
            parent = nodes.get(node.parent_id)
            if parent:
                parent.children.append(node)
        else:
            roots.append(node)

    return GlobalMindMap(user_id=user_id, thread_id=thread_id, roots=roots)
