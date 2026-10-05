#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import subprocess

logger = logging.getLogger("Unmanic.Plugin.strip_data_streams")


def has_data_stream(path):
    """Return True when ffprobe reports at least one data stream."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "stream=codec_type",
                "-of", "json",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )

        probe = json.loads(result.stdout)

        return any(
            stream.get("codec_type") == "data"
            for stream in probe.get("streams", [])
        )

    except Exception as exc:
        logger.error("Unable to probe '%s': %s", path, exc)
        return False


def on_library_management_file_test(data):
    """
    Add files containing data streams to the pending task list.
    """
    abspath = data.get("path")

    if abspath and has_data_stream(abspath):
        data["add_file_to_pending_tasks"] = True
        logger.debug(
            "Data stream detected in '%s'. Adding file to pending tasks.",
            abspath,
        )

    return data


def on_worker_process(data):
    """
    Losslessly remux the file while excluding all data streams.
    """
    data["exec_command"] = []
    data["repeat"] = False

    file_in = data.get("file_in")
    file_out = data.get("file_out")

    if not file_in or not file_out:
        return data

    if not has_data_stream(file_in):
        return data

    logger.info("Removing data streams from '%s'", file_in)

    data["exec_command"] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "info",
        "-i", file_in,

        # Map everything except data streams
        "-map", "0",
        "-map", "-0:d",

        # Preserve metadata, but drop chapters.
        # MP4/M4V chapters may be represented as a text/bin_data stream.
        "-map_metadata", "0",
        "-map_chapters", "-1",

        # No transcoding
        "-c", "copy",

        "-y",
        file_out,
    ]

    return data
