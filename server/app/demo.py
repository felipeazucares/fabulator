import uuid
from typing import Tuple

from .models import CreateNodeRequest, CreateWorkRequest, NodeType

# Placeholder work_id used by build_demo_tree; overwritten in _seed_with_transaction()
_PLACEHOLDER_WORK_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000000"))


def build_demo_tree(account_id: str, author: str) -> Tuple[CreateWorkRequest, list[CreateNodeRequest]]:
    """
    Pure function that returns the canonical demo content definition.

    Generates unique UUIDs for every node and wires up parent_id references
    so the tree is fully navigable on creation. No I/O -- single source of
    demo content.

    Returns:
        Tuple of (work_data, node_list) where work_data is a CreateWorkRequest
        and node_list is a list of CreateNodeRequest instances with all adjacency
        fields populated. Each node has a unique node_id for identification.
    """
    # Demo work data
    work = CreateWorkRequest(
        title="Demo: The Lighthouse at the End of the World",
        description="A story about a lighthouse keeper who discovers a mysterious signal.",
        author=author,
        tags=["fiction", "mystery"]
    )

    # Generate unique UUIDs for each node
    part1_id = str(uuid.uuid4())
    ch1_id = str(uuid.uuid4())
    ch2_id = str(uuid.uuid4())
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    s3_id = str(uuid.uuid4())
    s4_id = str(uuid.uuid4())
    b1_id = str(uuid.uuid4())
    b2_id = str(uuid.uuid4())
    b3_id = str(uuid.uuid4())
    b4_id = str(uuid.uuid4())

    b5_id = str(uuid.uuid4())
    b6_id = str(uuid.uuid4())
    b7_id = str(uuid.uuid4())
    b8_id = str(uuid.uuid4())

    # Define the tree structure with sibling groups
    # Each group is a list of (node_type, tag, description, text, child_group) tuples
    tree_structure = [
        # Part 1 (root) -> children: [Chapter 1, Chapter 2]
        {
            "node_id": part1_id,
            "node_type": NodeType.part,
            "parent_id": None,
            "tag": "The Lighthouse Keeper",
            "description": "Introduction to the main character and setting",
            "text": "In the remote coastal town of Millhaven, lived a lighthouse keeper named Thomas. The lighthouse stood tall on the rocky cliff, its beacon cutting through the foggy nights.",
            "tags": ["introduction", "character"],
            "children": [
                {
                    "node_id": ch1_id,
                    "node_type": NodeType.chapter,
                    "parent_id": part1_id,
                    "tag": "The Signal",
                    "description": "Thomas discovers an unusual signal from the lighthouse",
                    "text": "One evening, while checking the lighthouse equipment, Thomas noticed a strange pattern in the beacon. It wasn't the regular rotating light he was used to - it was a series of flashes that seemed to form a message.",
                    "tags": ["mystery", "signal"],
                    "children": [
                        {
                            "node_id": s1_id,
                            "node_type": NodeType.scene,
                            "parent_id": ch1_id,
                            "tag": "The First Night",
                            "description": "Thomas first notices the signal",
                            "text": "On his first night of observation, Thomas was struck by how clear the signal was. The flashes were perfectly timed and rhythmic.",
                            "tags": ["observation", "first night"],
                            "children": [
                                {
                                    "node_id": b1_id,
                                    "node_type": NodeType.beat,
                                    "parent_id": s1_id,
                                    "tag": "The Search Begins",
                                    "description": "Thomas starts the search for the signal sender",
                                    "text": "With his lantern and compass, Thomas began his search through the foggy night.",
                                    "tags": ["search", "beginning"],
                                    "children": []
                                },
                                {
                                    "node_id": b2_id,
                                    "node_type": NodeType.beat,
                                    "parent_id": s1_id,
                                    "tag": "The Discovery",
                                    "description": "Thomas discovers the signal sender",
                                    "text": "After hours of searching, Thomas found a small boat stranded on the rocks.",
                                    "tags": ["discovery", "boat"],
                                    "children": []
                                }
                            ]
                        },
                        {
                            "node_id": s2_id,
                            "node_type": NodeType.scene,
                            "parent_id": ch1_id,
                            "tag": "The Pattern",
                            "description": "Thomas decodes the signal pattern",
                            "text": "After several nights of careful observation, Thomas realized that the flashes formed a pattern - they were spelling out letters in Morse code.",
                            "tags": ["decoding", "pattern"],
                            "children": [
                                {
                                    "node_id": b3_id,
                                    "node_type": NodeType.beat,
                                    "parent_id": s2_id,
                                    "tag": "The Rescue",
                                    "description": "Thomas rescues the signal sender",
                                    "text": "Inside the boat, Thomas found a young woman who had been lost at sea.",
                                    "tags": ["rescue", "woman"],
                                    "children": []
                                },
                                {
                                    "node_id": b4_id,
                                    "node_type": NodeType.beat,
                                    "parent_id": s2_id,
                                    "tag": "The Return",
                                    "description": "Thomas returns the woman to safety",
                                    "text": "With the help of the local coast guard, Thomas returned the woman safely to shore.",
                                    "tags": ["return", "safety"],
                                    "children": []
                                }
                            ]
                        }
                    ]
                },
                {
                    "node_id": ch2_id,
                    "node_type": NodeType.chapter,
                    "parent_id": part1_id,
                    "tag": "The Investigation",
                    "description": "Thomas begins investigating the signal",
                    "text": "Determined to understand what he had seen, Thomas spent the next few nights observing the lighthouse. He noted that the signal pattern was consistent - it came every night at exactly 11:47 PM.",
                    "tags": ["investigation", "mystery"],
                    "children": [
                        {
                            "node_id": s3_id,
                            "node_type": NodeType.scene,
                            "parent_id": ch2_id,
                            "tag": "The Message",
                            "description": "Thomas discovers the message content",
                            "text": "The message read: 'Help needed. Lighthouse keeper. Signal 1234.' Thomas realized someone was in trouble.",
                            "tags": ["message", "help"],
                            "children": [
                                {
                                    "node_id": b5_id,
                                    "node_type": NodeType.beat,
                                    "parent_id": s3_id,
                                    "tag": "The Decision",
                                    "description": "Thomas decides to follow the signal coordinates",
                                    "text": "Armed with the message and his knowledge of the waters, Thomas prepared his boat for a journey into the storm.",
                                    "tags": ["decision", "journey"],
                                    "children": []
                                },
                                {
                                    "node_id": b6_id,
                                    "node_type": NodeType.beat,
                                    "parent_id": s3_id,
                                    "tag": "The Storm",
                                    "description": "Thomas faces a sudden storm during the investigation",
                                    "text": "A fierce storm rolled in as Thomas set out, making it difficult for him to see and navigate. But he pressed on, driven by the urgent message.",
                                    "tags": ["storm", "courage"],
                                    "children": []
                                }
                            ]
                        },
                        {
                            "node_id": s4_id,
                            "node_type": NodeType.scene,
                            "parent_id": ch2_id,
                            "tag": "The Rescue",
                            "description": "Thomas attempts to rescue the signal sender",
                            "text": "Thomas decided to act on the message. He organized a search party and set out to find who needed help.",
                            "tags": ["rescue", "action"],
                            "children": [
                                {
                                    "node_id": b7_id,
                                    "node_type": NodeType.beat,
                                    "parent_id": s4_id,
                                    "tag": "The Departure",
                                    "description": "Thomas and the search party set out",
                                    "text": "With the coordinates from the message, Thomas led the search party into the treacherous waters, hoping they would reach the stranded person in time.",
                                    "tags": ["departure", "search"],
                                    "children": []
                                },
                                {
                                    "node_id": b8_id,
                                    "node_type": NodeType.beat,
                                    "parent_id": s4_id,
                                    "tag": "The Discovery",
                                    "description": "Thomas finds the signal sender",
                                    "text": "After hours of navigating through the storm, Thomas spotted a small raft with a lone figure waving frantically in the fading light.",
                                    "tags": ["discovery", "rescue"],
                                    "children": []
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]

    # Flatten the tree into a list of nodes, wiring up adjacency fields
    def flatten(nodes: list, parent_id=None) -> list[CreateNodeRequest]:
        result = []
        for i, node_def in enumerate(nodes):
            next_id = nodes[i + 1]["node_id"] if i + 1 < len(nodes) else None
            prev_id = nodes[i - 1]["node_id"] if i > 0 else None
            
            node = CreateNodeRequest(
                node_id=node_def["node_id"],
                work_id=_PLACEHOLDER_WORK_ID,
                node_type=node_def["node_type"],
                parent_id=parent_id,
                tag=node_def["tag"],
                description=node_def["description"],
                text=node_def["text"],
                previous=prev_id,
                next=next_id,
                tags=node_def.get("tags", []),
            )
            result.append(node)
            
            # Recursively flatten children
            if node_def.get("children"):
                result.extend(flatten(node_def["children"], parent_id=node_def["node_id"]))
        return result

    nodes = flatten(tree_structure)

    return work, nodes
