import logging
from typing import Any, AsyncIterator, Dict, Optional, Sequence, Union

import orjson
import requests
import json
from langchain_core.messages import AnyMessage, BaseMessage, message_chunk_to_message
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.runnables import Runnable, RunnableConfig
from langserve.serialization import WellKnownLCSerializer
import time

logger = logging.getLogger(__name__)

MessagesStream = AsyncIterator[Union[list[AnyMessage], str]]


async def astream_state(
    app: Runnable,
    input: Union[Sequence[AnyMessage], Dict[str, Any]],
    config: RunnableConfig,
) -> MessagesStream:
    """Stream messages from the runnable."""
    root_run_id: Optional[str] = None
    messages: dict[str, BaseMessage] = {}

    async for event in app.astream_events(
        input, config, version="v1", stream_mode="values", exclude_tags=["nostream"]
    ):
        if event["event"] == "on_chain_start" and not root_run_id:
            root_run_id = event["run_id"]
            yield root_run_id
        elif event["event"] == "on_chain_stream" and event["run_id"] == root_run_id:
            new_messages: list[BaseMessage] = []

            # event["data"]["chunk"] is a Sequence[AnyMessage] or a Dict[str, Any]
            state_chunk_msgs: Union[Sequence[AnyMessage], Dict[str, Any]] = event[
                "data"
            ]["chunk"]
            if isinstance(state_chunk_msgs, dict):
                state_chunk_msgs = event["data"]["chunk"]["messages"]

            for msg in state_chunk_msgs:
                msg_id = msg["id"] if isinstance(msg, dict) else msg.id
                if msg_id in messages and msg == messages[msg_id]:
                    continue
                else:
                    print('msg', msg)
                    messages[msg_id] = msg
                    new_messages.append(msg)
            if new_messages:
                yield new_messages
        elif event["event"] == "on_chat_model_stream":
            message: BaseMessage = event["data"]["chunk"]
            if message.id not in messages:
                messages[message.id] = message
            else:
                messages[message.id] += message
            yield [messages[message.id]]


_serializer = WellKnownLCSerializer()


async def to_sse(messages_stream: MessagesStream) -> AsyncIterator[dict]:
    """Consume the stream into an EventSourceResponse"""
    try:
        async for chunk in messages_stream:
            # EventSourceResponse expects a string for data
            # so after serializing into bytes, we decode into utf-8
            # to get a string.
            if isinstance(chunk, str):
                yield {
                    "event": "metadata",
                    "data": orjson.dumps({"run_id": chunk}).decode(),
                }
            else:
                yield {
                    "event": "data",
                    "data": _serializer.dumps(
                        [message_chunk_to_message(msg) for msg in chunk]
                    ).decode(),
                }
    except Exception:
        logger.warn("error in stream", exc_info=True)
        yield {
            "event": "error",
            # Do not expose the error message to the client since
            # the message may contain sensitive information.
            # We'll add client side errors for validation as well.
            "data": orjson.dumps(
                {"status_code": 500, "message": "Internal Server Error"}
            ).decode(),
        }

    # Send an end event to signal the end of the stream
    yield {"event": "end"}

async def to_sse_vapi(messages_stream: MessagesStream, thread_id = '1') -> AsyncIterator[dict]:
    """Consume the stream into an EventSourceResponse in VAPI format"""
    
    last_length = 0  # Initialize last message length to zero

    try:
        async for chunk in messages_stream:
            # EventSourceResponse expects a string for data
            # so after serializing into bytes, we decode into utf-8
            # to get a string.
            if isinstance(chunk, list):
                ai_message = chunk[0]

                if isinstance(ai_message, AIMessageChunk):
                    message = message_chunk_to_message(chunk[0])

                    # Calculate the new content based on the difference in length
                    new_content = message.content[last_length:]

                    # Update the length of the last message seen
                    last_length = len(message.content)

                    yield {
                        "data": orjson.dumps({
                            "id": thread_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "gpt-4-turbo",
                            "system_fingerprint": "fp_44709d6fcb",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": new_content},
                                    "logprobs": None,
                                    "finish_reason": None,
                                },
                            ],
                        }).decode()
                    }
                
    except Exception:
        logger.warn("error in stream", exc_info=True)
        yield {
            "event": "error",
            # Do not expose the error message to the client since
            # the message may contain sensitive information.
            # We'll add client side errors for validation as well.
            "data": orjson.dumps(
                {"status_code": 500, "message": "Internal Server Error"}
            ).decode(),
        }

    # Send an end event to signal the end of the stream
    yield {"event": "end"}