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
    part2_id = str(uuid.uuid4())
    ch1_id = str(uuid.uuid4())
    ch2_id = str(uuid.uuid4())
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    s3_id = str(uuid.uuid4())
    s4_id = str(uuid.uuid4())
    s5_id = str(uuid.uuid4())
    s6_id = str(uuid.uuid4())

    # Define the tree structure with sibling groups
    # Each group is a list of (node_type, tag, description, text, child_group) tuples
    tree_structure = [
        # Part 1 (root) -> children: [Scene 1, Chapter 1, Chapter 2]
        {
            "node_id": part1_id,
            "node_type": NodeType.part,
            "parent_id": None,
            "tag": "The Lighthouse Keeper",
            "description": "Introduction to the main character and setting",
            "text": "In the remote coastal town of Millhaven, lived a lighthouse keeper named Thomas. The lighthouse stood tall on the rocky cliff, its beacon cutting through the foggy nights.",
            "tags": ["introduction", "character"],
            "children": [
                # Direct Part->Scene path
                {
                    "node_id": s1_id,
                    "node_type": NodeType.scene,
                    "parent_id": part1_id,
                    "tag": "The First Signal",
                    "description": "Thomas first notices the mysterious signal",
                    "text": "On his first night of observation, Thomas was struck by how clear the signal was. The flashes were perfectly timed and rhythmic, spelling out a message he could not yet understand.",
                    "tags": ["observation", "first night"],
                    "children": []
                },
                # Standard Part->Chapter path
                {
                    "node_id": ch1_id,
                    "node_type": NodeType.chapter,
                    "parent_id": part1_id,
                    "tag": "The Investigation",
                    "description": "Thomas investigates the unusual signal",
                    "text": "Determined to understand what he had seen, Thomas spent the next few nights observing the lighthouse. He noted that the signal pattern was consistent - it came every night at exactly 11:47 PM.",
                    "tags": ["investigation", "mystery"],
                    "children": [
                        # Chapter->Part path (nested Part)
                        {
                            "node_id": part2_id,
                            "node_type": NodeType.part,
                            "parent_id": ch1_id,
                            "tag": "The Sailor's Tale",
                            "description": "A flashback story within the investigation",
                            "text": "During his investigation, Thomas recalled a story his grandfather once told him about a shipwreck off the coast many years ago. The old sailor's tale held a clue to the signal.",
                            "tags": ["flashback", "story"],
                            "children": [
                                # Part->Scene inside nested Part
                                {
                                    "node_id": s2_id,
                                    "node_type": NodeType.scene,
                                    "parent_id": part2_id,
                                    "tag": "The Lost Voyage",
                                    "description": "The story of the shipwreck",
                                    "text": "The ship had been carrying a valuable cargo when it was caught in a terrible storm. The crew sent out a distress signal, but by the time help arrived, the ship had vanished into the depths.",
                                    "tags": ["shipwreck", "history"],
                                    "children": []
                                }
                            ]
                        },
                        # Chapter->Scene path
                        {
                            "node_id": s3_id,
                            "node_type": NodeType.scene,
                            "parent_id": ch1_id,
                            "tag": "The Message",
                            "description": "Thomas decodes the signal",
                            "text": "After several nights of careful observation, Thomas realized that the flashes formed a pattern - they were spelling out letters in Morse code. The message read: 'Help needed. Lighthouse keeper. Signal 1234.'",
                            "tags": ["decoding", "message"],
                            "children": []
                        },
                        # Another Chapter->Scene path
                        {
                            "node_id": s4_id,
                            "node_type": NodeType.scene,
                            "parent_id": ch1_id,
                            "tag": "The Rescue",
                            "description": "Thomas organizes a rescue mission",
                            "text": "Thomas decided to act on the message. He organized a search party, armed with his lantern and compass, and set out into the treacherous waters to find who needed help.",
                            "tags": ["rescue", "action"],
                            "children": []
                        }
                    ]
                },
                # Second Part->Chapter path
                {
                    "node_id": ch2_id,
                    "node_type": NodeType.chapter,
                    "parent_id": part1_id,
                    "tag": "The Revelation",
                    "description": "The mystery unravels",
                    "text": "As Thomas pieced together the clues from the signal, the old sailor's tale, and his own observations, a larger picture began to emerge about what lay beneath the waves off Millhaven's coast.",
                    "tags": ["revelation", "mystery"],
                    "children": [
                        {
                            "node_id": s5_id,
                            "node_type": NodeType.scene,
                            "parent_id": ch2_id,
                            "tag": "The Truth",
                            "description": "Thomas discovers the truth behind the signal",
                            "text": "The signal was not a cry for help from the present, but a legacy message from the past, repeating automatically for decades. Thomas was the first person in generations to notice it and understand its meaning.",
                            "tags": ["truth", "discovery"],
                            "children": []
                        },
                        {
                            "node_id": s6_id,
                            "node_type": NodeType.scene,
                            "parent_id": ch2_id,
                            "tag": "The Farewell",
                            "description": "Thomas makes his peace with the past",
                            "text": "With the mystery solved, Thomas stood at the lighthouse one last time as the sun set. He had given the lost crew the recognition they deserved. The signal would continue, but now someone would remember.",
                            "tags": ["resolution", "farewell"],
                            "children": []
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
