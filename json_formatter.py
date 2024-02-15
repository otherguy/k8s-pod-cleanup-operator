from pythonjsonlogger import jsonlogger
import json

DATE_FORMAT_TIMEZONE = "%Y-%m-%dT%H:%M:%S.%fZ"

class JsonFormatter(jsonlogger.JsonFormatter):
    EXTRA_PREFIX = "extra_"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        del log_record["levelname"]
        del log_record["taskName"]

        self.set_extra_keys(record, log_record, self._skip_fields)

    @staticmethod
    def is_private_key(key):
        return hasattr(key, "startswith") and key.startswith("_")

    @staticmethod
    def is_extra_key(key):
        return hasattr(key, "startswith") and key.startswith(JsonFormatter.EXTRA_PREFIX)

    @staticmethod
    def set_extra_keys(record, log_record, reserved):
        """
        Add the extra data to the log record.
        prefix will be added to all custom tags.
        """
        record_items = list(record.__dict__.items())
        records_filtered_reserved = [item for item in record_items if item[0] not in reserved]
        records_filtered_private_attr = [item for item in records_filtered_reserved if
                                         not JsonFormatter.is_private_key(item[0]) and item[0] != "taskName"]


        log_record.setdefault('extra', {})

        for key, value in records_filtered_private_attr:
            if not JsonFormatter.is_extra_key(key):
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                log_record["extra"][key] = value
                log_record.pop(key, None)

        # Delete log_record["extra"] if it's empty
        if not log_record["extra"]:
            del log_record["extra"]
