#!/usr/bin/env python3
"""
seed.py — Fabulator API seed script
Creates a test user and a 10-node narrative tree based on Casablanca.
Idempotent — clears existing tree before seeding.
Second pass resolves previous/next node name references to UUIDs.

Usage:
    python seed.py

Requires:
    pip install httpx --break-system-packages

The API must be running at http://localhost:8000
"""

import httpx
import json
import sys

BASE_URL = "http://localhost:8000"

USER = {
    "name": {"firstname": "Rick", "surname": "Blaine"},
    "username": "rick_blaine",
    "password": "heresoflookingatyou",
    "account_id": None,
    "email": "rick@ricks-cafe.com",
    "disabled": False,
    "user_role": "user:reader user:writer tree:reader tree:writer usertype:writer",
    "user_type": "free",
}

TREE = [
    {
        "name": "Casablanca",
        "parent": None,
        "description": "Story root — Casablanca, 1941. The city is a crossroads for refugees fleeing Nazi Europe.",
        "text": "Everyone in Casablanca is waiting. For exit visas, for ships, for their luck to change.",
        "previous": None,
        "next": None,
        "tags": ["setting", "inciting incident", "world-building"],
    },
    {
        "name": "Rick's Café Américain",
        "parent": "Casablanca",
        "description": "Rick runs the most popular café in Casablanca. He claims to stick his neck out for nobody.",
        "text": "The café hums with desperation dressed up as pleasure. Rick watches from the bar. He always watches.",
        "previous": None,
        "next": None,
        "tags": ["location", "character", "exposition"],
    },
    {
        "name": "Ugarte's Scheme",
        "parent": "Rick's Café Américain",
        "description": "Ugarte has stolen letters of transit signed by de Gaulle — safe passage for anyone.",
        "text": "Ugarte presses the letters into Rick's hand before the police take him. Rick doesn't ask why he's trusting him.",
        "previous": None,
        "next": "Ilsa Arrives",
        "tags": ["object", "inciting incident", "plot device"],
    },
    {
        "name": "Ilsa Arrives",
        "parent": "Rick's Café Américain",
        "description": "Ilsa Lund walks in with Victor Laszlo. Rick hasn't seen her since Paris.",
        "text": "Sam starts playing 'As Time Goes By'. Rick's jaw sets. Of all the gin joints.",
        "previous": "Ugarte's Scheme",
        "next": None,
        "tags": ["character", "turning point", "romance"],
    },
    {
        "name": "The Paris Flashback",
        "parent": "Ilsa Arrives",
        "description": "Rick remembers Paris — the occupation, the last train, Ilsa not showing up.",
        "text": "She said she'd come. The train left. Rick never understood why until now.",
        "previous": None,
        "next": "Ilsa's Confession",
        "tags": ["backstory", "romance", "exposition"],
    },
    {
        "name": "Ilsa's Confession",
        "parent": "Ilsa Arrives",
        "description": "Ilsa tells Rick she was married to Laszlo before Paris. She thought he was dead.",
        "text": "She wasn't lying in Paris. She was lying to herself. Rick doesn't know what to do with that.",
        "previous": "The Paris Flashback",
        "next": None,
        "tags": ["character", "revelation", "romance"],
    },
    {
        "name": "Laszlo's Cause",
        "parent": "Casablanca",
        "description": "Victor Laszlo is the resistance leader the Nazis most want stopped. He needs the letters.",
        "text": "Laszlo doesn't beg. He states facts: the letters, the cause, the cost of failure. Rick listens.",
        "previous": None,
        "next": "Renault's Deal",
        "tags": ["character", "politics", "stakes"],
    },
    {
        "name": "Renault's Deal",
        "parent": "Laszlo's Cause",
        "description": "Captain Renault offers Rick a way out — hand over Laszlo, keep the café.",
        "text": "Renault is corrupt but not cruel. He gives Rick a choice and calls it a favour.",
        "previous": "Laszlo's Cause",
        "next": "The Airport",
        "tags": ["character", "moral choice", "tension"],
    },
    {
        "name": "The Airport",
        "parent": "Casablanca",
        "description": "Rick's plan: use the letters to get Ilsa and Laszlo out. Not himself.",
        "text": "Rick puts Ilsa on the plane. He tells her she'll regret it if she stays. Maybe she will. Maybe he will.",
        "previous": "Renault's Deal",
        "next": "A Beautiful Friendship",
        "tags": ["climax", "sacrifice", "turning point"],
    },
    {
        "name": "A Beautiful Friendship",
        "parent": "The Airport",
        "description": "Renault lets Rick walk. The cause matters more than procedure, today.",
        "text": "Renault drops the Vichy water. They walk into the fog. This could be the beginning.",
        "previous": "The Airport",
        "next": None,
        "tags": ["resolution", "character", "ending"],
    },
]


def create_user(client):
    print("Creating user...")
    r = client.post(f"{BASE_URL}/users", json=USER)
    if r.status_code == 200:
        print(f"  User created: {USER['username']}")
    else:
        print(f"  User may already exist ({r.status_code}) — attempting login anyway")


def get_token(client):
    print("Getting token...")
    r = client.post(
        f"{BASE_URL}/get_token",
        data={
            "username": USER["username"],
            "password": USER["password"],
            "scope": USER["user_role"],
        },
    )
    if r.status_code != 200:
        print(f"  Login failed: {r.status_code} {r.text}")
        sys.exit(1)
    token = r.json()["access_token"]
    print("  Token obtained.")
    return {"Authorization": f"Bearer {token}"}


def clear_tree(client, headers):
    print("Clearing existing data...")

    # Delete all saves first to prevent stale documents with null root
    r = client.delete(f"{BASE_URL}/saves", headers=headers)
    if r.status_code == 200:
        print("  Saves cleared.")
    else:
        print(f"  Could not clear saves ({r.status_code}) - continuing.")

    # Now delete the tree nodes
    r = client.get(f"{BASE_URL}/trees/root", headers=headers)
    if r.status_code == 404:
        print("  No existing tree found - skipping node clear.")
        return
    if r.status_code != 200:
        print(
            f"  Could not check for root node ({r.status_code}) - skipping node clear."
        )
        return
    root_id = r.json()["data"].get("root")
    if not root_id:
        print("  No root node found - skipping node clear.")
        return
    r = client.delete(f"{BASE_URL}/nodes/{root_id}", headers=headers)
    if r.status_code == 200:
        print(f"  Tree cleared (root {root_id} and all children deleted).")
    else:
        print(f"  Failed to clear tree nodes: {r.status_code} {r.text}")
        sys.exit(1)


def seed_tree(client, headers):
    print("Seeding narrative tree (pass 1 — structure)...")
    node_ids = {}

    for node in TREE:
        parent_name = node["parent"]
        parent_id = node_ids.get(parent_name)

        payload = {
            "description": node["description"],
            "text": node["text"],
            "tags": node.get("tags", []),
        }
        if parent_id:
            payload["parent"] = parent_id

        r = client.post(
            f"{BASE_URL}/nodes/{node['name']}", json=payload, headers=headers
        )

        if r.status_code == 200:
            node_id = r.json()["data"]["node"]["_identifier"]
            node_ids[node["name"]] = node_id
            print(f"  Created: '{node['name']}' ({node_id})")
        else:
            print(f"  Failed: '{node['name']}' — {r.status_code} {r.text}")

    return node_ids


def resolve_links(client, headers, node_ids):
    print("Resolving previous/next links (pass 2)...")
    for node in TREE:
        previous_name = node.get("previous")
        next_name = node.get("next")

        if not previous_name and not next_name:
            continue

        node_id = node_ids.get(node["name"])
        if not node_id:
            print(f"  Skipping '{node['name']}' — not created in pass 1.")
            continue

        payload = {}
        if previous_name:
            previous_id = node_ids.get(previous_name)
            if previous_id:
                payload["previous"] = previous_id
            else:
                print(
                    f"  Warning: could not resolve previous '{previous_name}' for '{node['name']}'"
                )
        if next_name:
            next_id = node_ids.get(next_name)
            if next_id:
                payload["next"] = next_id
            else:
                print(
                    f"  Warning: could not resolve next '{next_name}' for '{node['name']}'"
                )

        if payload:
            r = client.put(f"{BASE_URL}/nodes/{node_id}", json=payload, headers=headers)
            if r.status_code == 200:
                print(
                    f"  Linked: '{node['name']}' → prev={payload.get('previous', '—')} next={payload.get('next', '—')}"
                )
            else:
                print(f"  Failed to link '{node['name']}': {r.status_code} {r.text}")


def main():
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{BASE_URL}/health")
        if r.status_code != 200:
            print(f"API not reachable at {BASE_URL}")
            sys.exit(1)
        print(f"API healthy at {BASE_URL}")

        create_user(client)
        headers = get_token(client)
        clear_tree(client, headers)
        node_ids = seed_tree(client, headers)
        resolve_links(client, headers, node_ids)

    print(f"\nDone. {len(node_ids)} nodes created.")
    print(json.dumps(node_ids, indent=2))


if __name__ == "__main__":
    main()
