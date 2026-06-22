#! /usr/bin/env python3
# Copyright (c) FIRST and other WPILib contributors.
# Open Source Software; you can modify and/or share it under the terms of
# the WPILib BSD license file in the root directory of this project.

import logging

from .datalog import DataLogReader

import mmap
import sys
from datetime import datetime

if len(sys.argv) != 2:
    print("Usage: datalog_dump.py <file>", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
with open(sys.argv[1], "r") as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    reader = DataLogReader(mm)
    if not reader:
        print("not a log file", file=sys.stderr)
        sys.exit(1)

    entries = {}
    for record in reader:
        timestamp = record.timestamp / 1000000
        if record.isStart():
            try:
                data = record.getStartData()
                print(
                    f"Start({data.entry}, name='{data.name}', type='{data.type}', metadata='{data.metadata}') [{timestamp}]"
                )
                if data.entry in entries:
                    print("...DUPLICATE entry ID, overriding")
                entries[data.entry] = data
            except TypeError:
                print("Start(INVALID)")
        elif record.isFinish():
            try:
                entry = record.getFinishEntry()
                print(f"Finish({entry}) [{timestamp}]")
                if entry not in entries:
                    print("...ID not found")
                else:
                    del entries[entry]
            except TypeError:
                print("Finish(INVALID)")
        elif record.isSetMetadata():
            try:
                data = record.getSetMetadataData()
                print(f"SetMetadata({data.entry}, '{data.metadata}') [{timestamp}]")
                if data.entry not in entries:
                    print("...ID not found")
            except TypeError:
                print("SetMetadata(INVALID)")
        elif record.isControl():
            print("Unrecognized control record")
        else:
            print(f"Data({record.entry}, size={len(record.data)}) ", end="")
            entry = entries.get(record.entry)
            if entry is None:
                print("<ID not found>")
                continue
            print(f"<name='{entry.name}', type='{entry.type}'> [{timestamp}]")

            try:
                # handle systemTime specially
                if entry.name == "systemTime" and entry.type == "int64":
                    dt = datetime.fromtimestamp(record.getInteger() / 1000000)
                    print("  {:%Y-%m-%d %H:%M:%S.%f}".format(dt))
                    continue

                if entry.type == "double":
                    print(f"  {record.getDouble()}")
                elif entry.type == "int64":
                    print(f"  {record.getInteger()}")
                elif entry.type in ("string", "json"):
                    print(f"  '{record.getString()}'")
                elif entry.type == "msgpack":
                    print(f"  '{record.getMsgPack()}'")
                elif entry.type == "boolean":
                    print(f"  {record.getBoolean()}")
                elif entry.type == "boolean[]":
                    arr = record.getBooleanArray()
                    print(f"  {arr}")
                elif entry.type == "double[]":
                    arr = record.getDoubleArray()
                    print(f"  {arr}")
                elif entry.type == "float[]":
                    arr = record.getFloatArray()
                    print(f"  {arr}")
                elif entry.type == "int64[]":
                    arr = record.getIntegerArray()
                    print(f"  {arr}")
                elif entry.type == "string[]":
                    arr = record.getStringArray()
                    print(f"  {arr}")
            except TypeError:
                print("  invalid")
