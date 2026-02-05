"""ROS2 bridge for web interface using rclpy."""

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy, QoSHistoryPolicy
from rosidl_runtime_py.utilities import get_message

from message_utils import msg_to_dict, dict_to_msg, get_message_type_info, parse_message_type


@dataclass
class TopicInfo:
    """Information about a ROS2 topic."""
    name: str
    msg_type: str
    publishers: List[str] = field(default_factory=list)
    subscribers: List[str] = field(default_factory=list)


@dataclass
class NodeInfo:
    """Information about a ROS2 node."""
    name: str
    namespace: str
    publishers: List[str] = field(default_factory=list)
    subscribers: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)


class ROS2Bridge:
    """Bridge between ROS2 and the web interface."""

    def __init__(self):
        self._node: Optional[Node] = None
        self._spin_thread: Optional[threading.Thread] = None
        self._running = False
        self._subscriptions: Dict[str, Any] = {}
        self._publishers: Dict[str, Any] = {}
        self._message_callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def start(self):
        """Initialize and start the ROS2 node."""
        if self._running:
            return

        rclpy.init()
        self._node = rclpy.create_node('web_rqt_bridge')
        self._running = True

        # Start spinning in a background thread
        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()

        self._node.get_logger().info('ROS2 Bridge started')

    def stop(self):
        """Stop the ROS2 node."""
        self._running = False

        if self._node:
            self._node.destroy_node()
            self._node = None

        if rclpy.ok():
            rclpy.shutdown()

    def _spin(self):
        """Spin the node to process callbacks."""
        while self._running and rclpy.ok():
            node = self._node
            if node is None:
                break
            rclpy.spin_once(node, timeout_sec=0.1)

    def get_topics(self) -> List[TopicInfo]:
        """Get list of all topics with their message types."""
        if not self._node:
            return []

        topic_names_and_types = self._node.get_topic_names_and_types()
        topics = []

        for name, types in topic_names_and_types:
            msg_type = types[0] if types else 'unknown'

            # Get publisher and subscriber info
            pub_info = self._node.get_publishers_info_by_topic(name)
            sub_info = self._node.get_subscriptions_info_by_topic(name)

            publishers = [f"{info.node_namespace}/{info.node_name}".replace('//', '/')
                         for info in pub_info]
            subscribers = [f"{info.node_namespace}/{info.node_name}".replace('//', '/')
                          for info in sub_info]

            topics.append(TopicInfo(
                name=name,
                msg_type=msg_type,
                publishers=publishers,
                subscribers=subscribers
            ))

        return topics

    def get_topic_type(self, topic_name: str) -> Optional[Dict[str, Any]]:
        """Get the message type definition for a topic."""
        if not self._node:
            return None

        topic_names_and_types = self._node.get_topic_names_and_types()

        for name, types in topic_names_and_types:
            if name == topic_name and types:
                try:
                    msg_class = parse_message_type(types[0])
                    return {
                        'type': types[0],
                        'definition': get_message_type_info(msg_class)
                    }
                except Exception as e:
                    return {'type': types[0], 'error': str(e)}

        return None

    def get_nodes(self) -> List[NodeInfo]:
        """Get list of all nodes with their pub/sub info."""
        if not self._node:
            return []

        node_names_and_namespaces = self._node.get_node_names_and_namespaces()
        nodes = []

        for name, namespace in node_names_and_namespaces:
            # Skip our own node
            if name == 'web_rqt_bridge':
                continue

            try:
                pubs = self._node.get_publisher_names_and_types_by_node(name, namespace)
                subs = self._node.get_subscriber_names_and_types_by_node(name, namespace)
                services = self._node.get_service_names_and_types_by_node(name, namespace)

                nodes.append(NodeInfo(
                    name=name,
                    namespace=namespace,
                    publishers=[p[0] for p in pubs],
                    subscribers=[s[0] for s in subs],
                    services=[s[0] for s in services]
                ))
            except Exception:
                # Node might have disappeared
                continue

        return nodes

    def get_graph(self) -> Dict[str, Any]:
        """Get the node graph data for visualization."""
        nodes = self.get_nodes()
        topics = self.get_topics()

        graph_nodes = []
        graph_edges = []

        # Add nodes
        for node in nodes:
            full_name = f"{node.namespace}/{node.name}".replace('//', '/')
            graph_nodes.append({
                'id': full_name,
                'label': node.name,
                'type': 'node',
                'namespace': node.namespace
            })

        # Add topics as nodes
        topic_set: Set[str] = set()
        for topic in topics:
            if topic.name not in topic_set:
                topic_set.add(topic.name)
                graph_nodes.append({
                    'id': topic.name,
                    'label': topic.name.split('/')[-1],
                    'type': 'topic',
                    'msg_type': topic.msg_type
                })

        # Add edges
        for topic in topics:
            for pub in topic.publishers:
                if pub != '/web_rqt_bridge':
                    graph_edges.append({
                        'source': pub,
                        'target': topic.name,
                        'type': 'publishes'
                    })
            for sub in topic.subscribers:
                if sub != '/web_rqt_bridge':
                    graph_edges.append({
                        'source': topic.name,
                        'target': sub,
                        'type': 'subscribes'
                    })

        return {
            'nodes': graph_nodes,
            'edges': graph_edges
        }

    def subscribe(self, topic_name: str, callback: Callable[[str, Dict], None]) -> bool:
        """Subscribe to a topic and register a callback for messages."""
        if not self._node:
            return False

        with self._lock:
            # Add callback to the list
            if topic_name not in self._message_callbacks:
                self._message_callbacks[topic_name] = []
            self._message_callbacks[topic_name].append(callback)

            # If already subscribed, just add the callback
            if topic_name in self._subscriptions:
                return True

            # Get message type
            topic_names_and_types = self._node.get_topic_names_and_types()
            msg_type_str = None

            for name, types in topic_names_and_types:
                if name == topic_name and types:
                    msg_type_str = types[0]
                    break

            if not msg_type_str:
                return False

            try:
                msg_class = parse_message_type(msg_type_str)
            except Exception:
                return False

            # Create QoS profile that's compatible with most publishers
            qos = QoSProfile(
                reliability=QoSReliabilityPolicy.BEST_EFFORT,
                durability=QoSDurabilityPolicy.VOLATILE,
                history=QoSHistoryPolicy.KEEP_LAST,
                depth=10
            )

            def msg_callback(msg):
                try:
                    data = msg_to_dict(msg)
                    callbacks = self._message_callbacks.get(topic_name, [])
                    for cb in callbacks:
                        try:
                            cb(topic_name, data)
                        except Exception:
                            pass
                except Exception:
                    pass

            sub = self._node.create_subscription(
                msg_class,
                topic_name,
                msg_callback,
                qos
            )

            self._subscriptions[topic_name] = sub
            return True

    def unsubscribe(self, topic_name: str, callback: Optional[Callable] = None) -> bool:
        """Unsubscribe from a topic."""
        with self._lock:
            if topic_name not in self._subscriptions:
                return False

            if callback:
                # Remove specific callback
                if topic_name in self._message_callbacks:
                    try:
                        self._message_callbacks[topic_name].remove(callback)
                    except ValueError:
                        pass

                    # If there are still callbacks, don't destroy subscription
                    if self._message_callbacks[topic_name]:
                        return True

            # Remove all callbacks and subscription
            if topic_name in self._message_callbacks:
                del self._message_callbacks[topic_name]

            if self._node:
                self._node.destroy_subscription(self._subscriptions[topic_name])
            del self._subscriptions[topic_name]
            return True

    def publish(self, topic_name: str, msg_type_str: str, data: Dict[str, Any]) -> bool:
        """Publish a message to a topic."""
        if not self._node:
            return False

        try:
            msg_class = parse_message_type(msg_type_str)
        except Exception:
            return False

        need_discovery_wait = False

        with self._lock:
            # Create publisher if needed
            if topic_name not in self._publishers:
                qos = QoSProfile(
                    reliability=QoSReliabilityPolicy.RELIABLE,
                    durability=QoSDurabilityPolicy.VOLATILE,
                    history=QoSHistoryPolicy.KEEP_LAST,
                    depth=10
                )
                pub = self._node.create_publisher(msg_class, topic_name, qos)
                self._publishers[topic_name] = (pub, msg_class)
                need_discovery_wait = True

            pub, stored_class = self._publishers[topic_name]

        # Give time for discovery outside the lock
        if need_discovery_wait:
            time.sleep(0.1)

        # Convert dict to message and publish
        msg = dict_to_msg(data, stored_class)
        pub.publish(msg)
        return True


# Global instance
ros_bridge = ROS2Bridge()
