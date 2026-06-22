import logging
import sys

from typing import Iterator

from . import StructDecoder
from .datalog import DataLogReader

__all__ = ["DataLogDatum", "datalog_datum_iterator"]


class DataLogDatum:
    def __init__(self, name=None, timestamp=None, value=None):
        self.name = name
        self.timestamp = timestamp
        self.value = value

    def __str__(self):
        return f'{self.name} = {self.value} @ {self.timestamp}'


def datalog_datum_iterator(filename : str = None) -> Iterator[DataLogDatum]:
    """

    :param filename:
    :return: yields tuples of DataLogDatum, data type, raw data, and "is in record" boolean
    """
    import mmap
    from datetime import datetime

    sd = StructDecoder.StructDecoder()

    with open(filename, "r") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        reader = DataLogReader(mm)
        if not reader:
            logging.error("not a log file")
            sys.exit(1)

        entries = {}
        for record in reader:
            timestamp = record.timestamp / 1000000
            if record.isStart():
                try:
                    data = record.getStartData()
                    logging.debug(f"Start({data.entry}, name='{data.name}', type='{data.type}', metadata='{data.metadata}') [{timestamp}]")
                    if data.entry in entries:
                        # TODO
                        logging.warning("...DUPLICATE entry ID, overriding")
                    entries[data.entry] = data
                except TypeError:
                    logging.error("Start(INVALID)")
            elif record.isFinish():
                try:
                    entry = record.getFinishEntry()
                    logging.debug(f"Finish({entry}) [{timestamp}]")
                    if entry not in entries:
                        # TODO
                        logging.warning("...ID not found")
                    else:
                        del entries[entry]
                except TypeError:
                    logging.error("Finish(INVALID)")
            elif record.isSetMetadata():
                try:
                    data = record.getSetMetadataData()
                    logging.debug(f"SetMetadata({data.entry}, '{data.metadata}') [{timestamp}]")
                    if data.entry not in entries:
                        # TODO
                        logging.warning("...ID not found")
                except TypeError:
                    logging.error("SetMetadata(INVALID)")
            elif record.isControl():
                logging.error("Unrecognized control record")
            else:
                logging.debug(f"Data({record.entry}, size={len(record.data)}) ")
                entry = entries.get(record.entry)
                if entry is None:
                    logging.warning(" <ID '%s' not found>", record.entry)
                    continue
                logging.debug(f"<name='{entry.name}', type='{entry.type}'> [{timestamp}]")

                try:
                    rv = None
                    rt = entry.type
                    # handle systemTime specially
                    if entry.name == "systemTime" and entry.type == "int64":
                        rv = datetime.fromtimestamp(record.getInteger() / 1000000)
                        rt = "DATETIME"
                        # print("  {:%Y-%m-%d %H:%M:%S.%f}".format(dt))

                    elif entry.type == "double":
                        rv = record.getDouble()
                    elif entry.type == "int64":
                        rv = record.getInteger()
                    elif entry.type in ("string", "json"):
                        rv = record.getString()
                    elif entry.type == "msgpack":
                        rv = record.getMsgPack()
                    elif entry.type == "boolean":
                        rv = record.getBoolean()
                    elif entry.type == "boolean[]":
                        rv = record.getBooleanArray()
                    elif entry.type == "double[]":
                        rv = record.getDoubleArray()
                    elif entry.type == "float[]":
                        rv = record.getFloatArray()
                    elif entry.type == "int64[]":
                        rv = record.getIntegerArray()
                    elif entry.type == "string[]":
                        rv = record.getStringArray()
                    elif entry.type == 'structschema':
                        struct_schema_name = entry.name.removeprefix('/.schema/')
                        if len(record.data) == 0:
                            logging.warning("structschema '%s' is zero length", entry.name)
                            continue
                        sd.add_schema(struct_schema_name, record.data)
                        logging.debug("schema %s = %s", struct_schema_name, sd.schemas)
                    elif entry.type.startswith('struct:'):
                        try:
                            decoded = sd.decode(entry.type, record.data)
                        except ValueError as err:
                            logging.error("trouble decoding %s with struct '%s': %s", entry.name, entry.type, str(err))
                            continue
                        decoded_data = decoded.get('data')
                        schema = sd.schemas.get(entry.type)
                        if schema is None:
                            # impossible, I think
                            logging.error("StructDecoder had no schema named '%s'", entry.type)
                            continue
                        for data_item, value_schema in zip(decoded_data.values(), schema.value_schemas):
                            datum = DataLogDatum(entry.name + "/" + value_schema.name, timestamp=timestamp, value=data_item)
                            yield datum, value_schema.type, None, True
                    else:
                        logging.error(f"do not recognize type {entry.type}")
                    if rv is not None:
                        datum = DataLogDatum(name=entry.name, timestamp=timestamp, value=rv)
                        yield datum, rt, record.data, False
                finally:
                    pass


def main(argv):
    import argparse
    import mmap
    from datetime import datetime

    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('input')
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger('').setLevel(logging.DEBUG)

    for t in datalog_datum_iterator(args.input):
        datum = t[0]
        print(vars(datum))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    main(sys.argv[1:])
