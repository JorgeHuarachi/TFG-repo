"""Stable-ish ID utilities for the Indoor Data Model exporter."""

import re
import unicodedata


def normalize_token(value, fallback="ITEM"):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    return text or fallback


def ref(layer_id, container_id, object_id):
    return f"{layer_id}:{container_id}:{object_id}"


def node_id_for_cell(cell_id):
    if cell_id.startswith("CS_"):
        return "N_" + cell_id[3:]
    return "N_" + normalize_token(cell_id)


def edge_id_for_boundary(boundary_id):
    if boundary_id.startswith("CB_"):
        return "E_" + boundary_id[3:]
    return "E_" + normalize_token(boundary_id)


def compact_cell_token(cell_id):
    token = cell_id
    if token.startswith("CS_L00_"):
        token = token[len("CS_L00_"):]
    elif token.startswith("CS_"):
        token = token[len("CS_"):]
    return normalize_token(token)
