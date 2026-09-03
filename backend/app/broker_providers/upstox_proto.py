"""
Upstox Market Data Feed V3 Protobuf Message Architecture
=========================================================
Dynamically builds and compiles the authentic Upstox Feed V3 Protobuf
specification using standard google.protobuf descriptors.
Enables binary stream decoding with zero external binary compilation dependencies.
"""

import logging
from typing import Dict, Any, Optional
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

logger = logging.getLogger(__name__)

# Construct FileDescriptorProto for Upstox Market Data Feed V3
file_proto = descriptor_pb2.FileDescriptorProto()
file_proto.name = "MarketDataFeedV3.proto"
file_proto.package = "com.upstox.marketdatafeeder.rpc.proto"
file_proto.syntax = "proto3"

# 1. Type Enum
enum_type = file_proto.enum_type.add()
enum_type.name = "Type"
v0 = enum_type.value.add()
v0.name = "initial_feed"
v0.number = 0
v1 = enum_type.value.add()
v1.name = "live_feed"
v1.number = 1

# 2. LTPC Message
msg_ltpc = file_proto.message_type.add()
msg_ltpc.name = "LTPC"
f = msg_ltpc.field.add()
f.name, f.number, f.type = "ltp", 1, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_ltpc.field.add()
f.name, f.number, f.type = "ltt", 2, descriptor_pb2.FieldDescriptorProto.TYPE_INT64
f = msg_ltpc.field.add()
f.name, f.number, f.type = "ltq", 3, descriptor_pb2.FieldDescriptorProto.TYPE_INT64
f = msg_ltpc.field.add()
f.name, f.number, f.type = "cp", 4, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE

# 3. MarketLevel Message (Bid/Ask)
msg_ml = file_proto.message_type.add()
msg_ml.name = "MarketLevel"
f = msg_ml.field.add()
f.name, f.number, f.type = "bid_quantity", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT32
f = msg_ml.field.add()
f.name, f.number, f.type = "bid_price", 2, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_ml.field.add()
f.name, f.number, f.type = "ask_quantity", 3, descriptor_pb2.FieldDescriptorProto.TYPE_INT32
f = msg_ml.field.add()
f.name, f.number, f.type = "ask_price", 4, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE

# 4. MarketOHLC Message
msg_ohlc = file_proto.message_type.add()
msg_ohlc.name = "MarketOHLC"
f = msg_ohlc.field.add()
f.name, f.number, f.type = "open", 1, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_ohlc.field.add()
f.name, f.number, f.type = "high", 2, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_ohlc.field.add()
f.name, f.number, f.type = "low", 3, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_ohlc.field.add()
f.name, f.number, f.type = "close", 4, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE

# 5. ExtendedFeedDetails Message
msg_efd = file_proto.message_type.add()
msg_efd.name = "ExtendedFeedDetails"
f = msg_efd.field.add()
f.name, f.number, f.type = "atp", 1, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_efd.field.add()
f.name, f.number, f.type = "cp", 2, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_efd.field.add()
f.name, f.number, f.type = "v", 3, descriptor_pb2.FieldDescriptorProto.TYPE_INT64
f = msg_efd.field.add()
f.name, f.number, f.type = "oi", 4, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_efd.field.add()
f.name, f.number, f.type = "change", 5, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_efd.field.add()
f.name, f.number, f.type = "change_percent", 6, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_efd.field.add()
f.name, f.number, f.type = "upper_circuit", 7, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_efd.field.add()
f.name, f.number, f.type = "lower_circuit", 8, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_efd.field.add()
f.name, f.number, f.type = "week52_high", 9, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
f = msg_efd.field.add()
f.name, f.number, f.type = "week52_low", 10, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE

# 6. MarketFullFeed Message
msg_mff = file_proto.message_type.add()
msg_mff.name = "MarketFullFeed"
f = msg_mff.field.add()
f.name, f.number, f.type, f.type_name = "ltpc", 1, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.LTPC"
f = msg_mff.field.add()
f.name, f.number, f.type, f.type_name = "ohlc", 2, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.MarketOHLC"
f = msg_mff.field.add()
f.name, f.number, f.type, f.type_name = "market_level", 3, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.MarketLevel"
f = msg_mff.field.add()
f.name, f.number, f.type, f.type_name = "efd", 4, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.ExtendedFeedDetails"

# 7. IndexFullFeed Message
msg_iff = file_proto.message_type.add()
msg_iff.name = "IndexFullFeed"
f = msg_iff.field.add()
f.name, f.number, f.type, f.type_name = "ltpc", 1, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.LTPC"
f = msg_iff.field.add()
f.name, f.number, f.type, f.type_name = "ohlc", 2, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.MarketOHLC"
f = msg_iff.field.add()
f.name, f.number, f.type, f.type_name = "efd", 3, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.ExtendedFeedDetails"

# 8. FullFeed Message
msg_ff = file_proto.message_type.add()
msg_ff.name = "FullFeed"
f = msg_ff.field.add()
f.name, f.number, f.type, f.type_name = "market_full_feed", 1, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.MarketFullFeed"
f = msg_ff.field.add()
f.name, f.number, f.type, f.type_name = "index_full_feed", 2, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.IndexFullFeed"

# 9. Feed Message
msg_feed = file_proto.message_type.add()
msg_feed.name = "Feed"
f = msg_feed.field.add()
f.name, f.number, f.type, f.type_name = "ltpc", 1, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.LTPC"
f = msg_feed.field.add()
f.name, f.number, f.type, f.type_name = "full_feed", 2, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.FullFeed"

# 10. FeedResponse Message (contains map<string, Feed> feeds)
msg_resp = file_proto.message_type.add()
msg_resp.name = "FeedResponse"
f = msg_resp.field.add()
f.name, f.number, f.type, f.type_name = "type", 1, descriptor_pb2.FieldDescriptorProto.TYPE_ENUM, ".com.upstox.marketdatafeeder.rpc.proto.Type"

# Map entry message for feeds map
map_entry = msg_resp.nested_type.add()
map_entry.name = "FeedsEntry"
map_entry.options.map_entry = True
kf = map_entry.field.add()
kf.name, kf.number, kf.type = "key", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING
vf = map_entry.field.add()
vf.name, vf.number, vf.type, vf.type_name = "value", 2, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.Feed"

f = msg_resp.field.add()
f.name, f.number, f.type, f.type_name = "feeds", 2, descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".com.upstox.marketdatafeeder.rpc.proto.FeedResponse.FeedsEntry"
f.label = descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED

f = msg_resp.field.add()
f.name, f.number, f.type = "current_timestamp", 3, descriptor_pb2.FieldDescriptorProto.TYPE_INT64

# Register into DescriptorPool
_pool = descriptor_pool.DescriptorPool()
_pool.Add(file_proto)

# Instantiate Message Classes
FeedResponse = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.FeedResponse"))
Feed = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.Feed"))
FullFeed = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.FullFeed"))
MarketFullFeed = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.MarketFullFeed"))
IndexFullFeed = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.IndexFullFeed"))
LTPC = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.LTPC"))
MarketOHLC = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.MarketOHLC"))
MarketLevel = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.MarketLevel"))
ExtendedFeedDetails = message_factory.GetMessageClass(_pool.FindMessageTypeByName("com.upstox.marketdatafeeder.rpc.proto.ExtendedFeedDetails"))


def decode_upstox_protobuf_frame(binary_data: bytes) -> Optional[Dict[str, Any]]:
    """
    Decodes an authentic Upstox binary websocket frame into a structured dictionary.
    """
    try:
        resp = FeedResponse()
        resp.ParseFromString(binary_data)

        feeds_dict = {}
        for key, feed_obj in resp.feeds.items():
            feed_dict = {}
            if feed_obj.HasField("ltpc"):
                feed_dict["ltpc"] = {
                    "ltp": feed_obj.ltpc.ltp,
                    "ltt": feed_obj.ltpc.ltt,
                    "ltq": feed_obj.ltpc.ltq,
                    "cp": feed_obj.ltpc.cp,
                }
            elif feed_obj.HasField("full_feed"):
                ff = feed_obj.full_feed
                if ff.HasField("market_full_feed"):
                    mff = ff.market_full_feed
                    feed_dict["ff"] = {
                        "marketFF": {
                            "ltpc": {
                                "ltp": mff.ltpc.ltp,
                                "ltt": mff.ltpc.ltt,
                                "ltq": mff.ltpc.ltq,
                                "cp": mff.ltpc.cp,
                            },
                            "ohlc": {
                                "open": mff.ohlc.open,
                                "high": mff.ohlc.high,
                                "low": mff.ohlc.low,
                                "close": mff.ohlc.close,
                            },
                            "v": mff.efd.v if mff.HasField("efd") else 0,
                            "eoi": int(mff.efd.oi) if mff.HasField("efd") else 0,
                        }
                    }
                    if mff.HasField("market_level"):
                        feed_dict["market_level"] = {
                            "bid_price": mff.market_level.bid_price,
                            "bid_quantity": mff.market_level.bid_quantity,
                            "ask_price": mff.market_level.ask_price,
                            "ask_quantity": mff.market_level.ask_quantity,
                        }
                elif ff.HasField("index_full_feed"):
                    iff = ff.index_full_feed
                    feed_dict["ff"] = {
                        "marketFF": {
                            "ltpc": {
                                "ltp": iff.ltpc.ltp,
                                "ltt": iff.ltpc.ltt,
                                "cp": iff.ltpc.cp,
                            },
                            "ohlc": {
                                "open": iff.ohlc.open,
                                "high": iff.ohlc.high,
                                "low": iff.ohlc.low,
                                "close": iff.ohlc.close,
                            },
                        }
                    }
            feeds_dict[key] = feed_dict

        return {
            "feeds": feeds_dict,
            "current_timestamp": resp.current_timestamp,
        }
    except Exception as exc:
        logger.debug(f"[UPSTOX PROTOBUF DECODER] Binary decode error: {exc}")
        return None
