"""Utilities for converting ROS2 messages to/from JSON."""

import array
import numpy as np
from typing import Any, Dict, Type
from rosidl_runtime_py.utilities import get_message as get_message_class


def msg_to_dict(msg: Any) -> Dict[str, Any]:
    """Convert a ROS2 message to a JSON-serializable dictionary."""
    if msg is None:
        return None

    result = {}

    # Get all slots (fields) of the message
    for field_name in msg.get_fields_and_field_types().keys():
        value = getattr(msg, field_name)
        result[field_name] = _convert_value(value)

    return result


def _convert_value(value: Any) -> Any:
    """Convert a single value to JSON-serializable format."""
    if value is None:
        return None

    # Handle primitive types
    if isinstance(value, (bool, int, float, str)):
        return value

    # Handle bytes
    if isinstance(value, bytes):
        return list(value)

    # Handle numpy arrays
    if isinstance(value, np.ndarray):
        return value.tolist()

    # Handle array.array
    if isinstance(value, array.array):
        return list(value)

    # Handle lists/tuples
    if isinstance(value, (list, tuple)):
        return [_convert_value(item) for item in value]

    # Handle nested messages (check if it has get_fields_and_field_types)
    if hasattr(value, 'get_fields_and_field_types'):
        return msg_to_dict(value)

    # Fallback: convert to string
    return str(value)


def dict_to_msg(data: Dict[str, Any], msg_type: Type) -> Any:
    """Convert a dictionary to a ROS2 message."""
    msg = msg_type()

    field_types = msg.get_fields_and_field_types()

    for field_name, value in data.items():
        if field_name not in field_types:
            continue

        field_type_str = field_types[field_name]
        current_value = getattr(msg, field_name)

        converted = _convert_to_ros_type(value, field_type_str, current_value)
        setattr(msg, field_name, converted)

    return msg


def _convert_to_ros_type(value: Any, field_type_str: str, current_value: Any) -> Any:
    """Convert a JSON value to the appropriate ROS2 type."""
    if value is None:
        return current_value

    # Handle sequences
    if field_type_str.startswith('sequence<'):
        inner_type = field_type_str[9:-1]
        if isinstance(value, list):
            return [_convert_primitive(item, inner_type) for item in value]
        return value

    # Handle arrays (fixed size)
    if '[' in field_type_str:
        base_type = field_type_str.split('[')[0]
        if isinstance(value, list):
            return [_convert_primitive(item, base_type) for item in value]
        return value

    # Handle nested messages
    if hasattr(current_value, 'get_fields_and_field_types'):
        if isinstance(value, dict):
            return dict_to_msg(value, type(current_value))
        return current_value

    # Handle primitives
    return _convert_primitive(value, field_type_str)


def _convert_primitive(value: Any, type_str: str) -> Any:
    """Convert a value to a primitive ROS2 type."""
    if value is None:
        return value

    type_map = {
        'bool': bool,
        'int8': int,
        'uint8': int,
        'int16': int,
        'uint16': int,
        'int32': int,
        'uint32': int,
        'int64': int,
        'uint64': int,
        'float': float,
        'float32': float,
        'float64': float,
        'double': float,
        'string': str,
        'wstring': str,
    }

    if type_str in type_map:
        try:
            return type_map[type_str](value)
        except (ValueError, TypeError):
            return value

    return value


def get_message_type_info(msg_type: Type) -> Dict[str, Any]:
    """Get information about a message type's structure."""
    if not hasattr(msg_type, 'get_fields_and_field_types'):
        return {'type': str(msg_type)}

    fields = {}
    msg_instance = msg_type()

    for field_name, field_type in msg_instance.get_fields_and_field_types().items():
        field_value = getattr(msg_instance, field_name)

        if hasattr(field_value, 'get_fields_and_field_types'):
            fields[field_name] = {
                'type': field_type,
                'nested': get_message_type_info(type(field_value))
            }
        else:
            fields[field_name] = {'type': field_type}

    return {'fields': fields}


def parse_message_type(type_string: str) -> Type:
    """Parse a message type string and return the message class."""
    try:
        return get_message_class(type_string)
    except Exception:
        # Try alternate parsing for types like 'std_msgs/msg/String'
        parts = type_string.replace('/', '.')
        if '/msg/' in type_string:
            parts = type_string.split('/')
            if len(parts) == 3:
                return get_message_class(f"{parts[0]}/{parts[1]}/{parts[2]}")
        raise
