from typing import Tuple
from .models import CreateWorkRequest, NodeType, NodeResponse, WorkResponse
from datetime import datetime, timezone


def build_demo_tree(account_id: str, author: str) -> Tuple[CreateWorkRequest, list]:
    """
    Pure function that returns the canonical demo content definition.
    
    Returns:
        Tuple of (work_data, node_list) where work_data is a CreateWorkRequest
        and node_list is a list of NodeCreate objects.
    """
    # Demo work data
    work = CreateWorkRequest(
        title="Demo: The Lighthouse at the End of the World",
        description="A story about a lighthouse keeper who discovers a mysterious signal.",
        author=author,
        tags=["demo", "fiction", "mystery"]
    )
    
    # Demo nodes - building a tree with part/chapter/scene/beat structure
    nodes = [
        # Part 1
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.part,
            "parent_id": None,
            "tag": "The Lighthouse Keeper",
            "description": "Introduction to the main character and setting",
            "text": "In the remote coastal town of Millhaven, lived a lighthouse keeper named Thomas. The lighthouse stood tall on the rocky cliff, its beacon cutting through the foggy nights.",
            "previous": None,
            "next": None,
            "tags": ["introduction", "character"]
        },
        # Chapter 1
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.chapter,
            "parent_id": "00000000-0000-0000-0000-000000000001",
            "tag": "The Signal",
            "description": "Thomas discovers an unusual signal from the lighthouse",
            "text": "One evening, while checking the lighthouse equipment, Thomas noticed a strange pattern in the beacon. It wasn't the regular rotating light he was used to - it was a series of flashes that seemed to form a message.",
            "previous": None,
            "next": None,
            "tags": ["mystery", "signal"]
        },
        # Chapter 2
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.chapter,
            "parent_id": "00000000-0000-0000-0000-000000000001",
            "tag": "The Investigation",
            "description": "Thomas begins investigating the signal",
            "text": "Determined to understand what he had seen, Thomas spent the next few nights observing the lighthouse. He noted that the signal pattern was consistent - it came every night at exactly 11:47 PM.",
            "previous": None,
            "next": None,
            "tags": ["investigation", "mystery"]
        },
        # Scene 1
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.scene,
            "parent_id": "00000000-0000-0000-0000-000000000002",
            "tag": "The First Night",
            "description": "Thomas first notices the signal",
            "text": "On his first night of observation, Thomas was struck by how clear the signal was. The flashes were perfectly timed and rhythmic.",
            "previous": None,
            "next": None,
            "tags": ["observation", "first night"]
        },
        # Scene 2
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.scene,
            "parent_id": "00000000-0000-0000-0000-000000000002",
            "tag": "The Pattern",
            "description": "Thomas decodes the signal pattern",
            "text": "After several nights of careful observation, Thomas realized that the flashes formed a pattern - they were spelling out letters in Morse code.",
            "previous": None,
            "next": None,
            "tags": ["decoding", "pattern"]
        },
        # Scene 3
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.scene,
            "parent_id": "00000000-0000-0000-0000-000000000003",
            "tag": "The Message",
            "description": "Thomas discovers the message content",
            "text": "The message read: 'Help needed. Lighthouse keeper. Signal 1234.' Thomas realized someone was in trouble.",
            "previous": None,
            "next": None,
            "tags": ["message", "help"]
        },
        # Scene 4
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.scene,
            "parent_id": "00000000-0000-0000-0000-000000000003",
            "tag": "The Rescue",
            "description": "Thomas attempts to rescue the signal sender",
            "text": "Thomas decided to act on the message. He organized a search party and set out to find who needed help.",
            "previous": None,
            "next": None,
            "tags": ["rescue", "action"]
        },
        # Beat 1
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.beat,
            "parent_id": "00000000-0000-0000-0000-000000000004",
            "tag": "The Search Begins",
            "description": "Thomas starts the search for the signal sender",
            "text": "With his lantern and compass, Thomas began his search through the foggy night.",
            "previous": None,
            "next": None,
            "tags": ["search", "beginning"]
        },
        # Beat 2
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.beat,
            "parent_id": "00000000-0000-0000-0000-000000000004",
            "tag": "The Discovery",
            "description": "Thomas discovers the signal sender",
            "text": "After hours of searching, Thomas found a small boat stranded on the rocks.",
            "previous": None,
            "next": None,
            "tags": ["discovery", "boat"]
        },
        # Beat 3
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.beat,
            "parent_id": "00000000-0000-0000-0000-000000000005",
            "tag": "The Rescue",
            "description": "Thomas rescues the signal sender",
            "text": "Inside the boat, Thomas found a young woman who had been lost at sea.",
            "previous": None,
            "next": None,
            "tags": ["rescue", "woman"]
        },
        # Beat 4
        {
            "work_id": "00000000-0000-0000-0000-000000000001",
            "node_type": NodeType.beat,
            "parent_id": "00000000-0000-0000-0000-000000000005",
            "tag": "The Return",
            "description": "Thomas returns the woman to safety",
            "text": "With the help of the local coast guard, Thomas returned the woman safely to shore.",
            "previous": None,
            "next": None,
            "tags": ["return", "safety"]
        }
    ]
    
    return work, nodes