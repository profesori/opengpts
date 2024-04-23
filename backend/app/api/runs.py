from typing import Any, Dict, Optional, Sequence, Union

import langsmith.client
from fastapi import APIRouter, BackgroundTasks, HTTPException, Body
from fastapi.exceptions import RequestValidationError
from langchain.pydantic_v1 import ValidationError
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langserve.schema import FeedbackCreateRequest
from langsmith.utils import tracing_is_enabled
from pydantic import BaseModel, Field
from sse_starlette import EventSourceResponse
from typing import Annotated
from langchain_community.chat_message_histories import RedisChatMessageHistory
import os

from app.agent import agent
from app.auth.handlers import AuthedUser
from app.storage import get_assistant, get_thread, put_thread
from app.stream import astream_state, to_sse, to_sse_vapi

from pydantic import BaseModel
from langchain_core.prompts import PromptTemplate
from app.llms import (
    get_openai_llm,
    get_groq_llm
)
from langchain_core.runnables import RunnablePassthrough
from app.tools import get_retriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever
from langchain.chains.combine_documents import create_stuff_documents_chain

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.chains import create_retrieval_chain

router = APIRouter()


# Define the request and response models
class MessageRequest(BaseModel):
    message: str
    id: Optional[str] = None

class MessageResponse(BaseModel):
    response: str

class CreateRunPayload(BaseModel):
    """Payload for creating a run."""

    thread_id: str
    input: Optional[Union[Sequence[AnyMessage], Dict[str, Any]]] = Field(
        default_factory=dict
    )
    config: Optional[RunnableConfig] = None


async def _run_input_and_config(payload: Union[CreateRunPayload, dict], user_id: str, force_thread_creation: bool = False, assistant_id: Optional[str] = None, messages: Optional[list] = None):
    thread_id = getattr(payload, 'thread_id', None) or payload['id']

    if (not getattr(payload, 'input', None)):
        print(payload, messages[-1], type(messages[-1]))
        input = {
            "messages": [
                {
                    "content": messages[-1]['content'],
                    "additional_kwargs": {},
                    "type": "human",
                    "example": False,
                    "id": "human-0.17093995759986003"
                }
            ]
        }
    else: 
        input = payload.input
    
    thread = await get_thread(user_id, thread_id)
    if not thread:
        if (not force_thread_creation):
            raise HTTPException(status_code=404, detail="Thread not found")
        thread = await put_thread(
            user_id,
            thread_id=thread_id,
            assistant_id=assistant_id,
            name="",
        )

    assistant = await get_assistant(user_id, str(thread["assistant_id"]))
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")

    config: RunnableConfig = {
        **assistant["config"],
        "configurable": {
            **assistant["config"]["configurable"],
            **((getattr(payload, 'config', None)or {}).get("configurable") or {}),
            "user_id": user_id,
            "thread_id": str(thread["thread_id"]),
            "assistant_id": str(assistant["assistant_id"]),
        },
    }

    try:
        if input is not None:
            agent.get_input_schema(config).validate(input)
    except ValidationError as e:
        raise RequestValidationError(e.errors(), body=payload)

    return input, config


@router.post("")
async def create_run(
    payload: CreateRunPayload,
    user: AuthedUser,
    background_tasks: BackgroundTasks,
):
    """Create a run."""
    input_, config = await _run_input_and_config(payload, user["user_id"])
    background_tasks.add_task(agent.ainvoke, input_, config)
    return {"status": "ok"}  # TODO add a run id


@router.post("/stream")
async def stream_run(
    payload: CreateRunPayload,
    user: AuthedUser,
):
    """Create a run."""
    input_, config = await _run_input_and_config(payload, user["user_id"])

    return EventSourceResponse(to_sse(astream_state(agent, input_, config)))

@router.post("/{assistant_id}/chat/completions")
async def stream_run_vapi(
    user: AuthedUser,
    assistant_id: str,
    call: Annotated[dict, Body()],
    messages: Annotated[list, Body()],
):
    input_, config = await _run_input_and_config(call, user["user_id"], force_thread_creation=True, assistant_id=assistant_id, messages=messages)

    return EventSourceResponse(to_sse_vapi(astream_state(agent, input_, config)))

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

@router.post("/{assistant_id}/chat")
async def chat(request: MessageRequest, assistant_id: str):
    print('Request Designa', request)
    try:
        llm = get_groq_llm()
        retriever = get_retriever(assistant_id, thread_id="1")
    
        ## Contextualize question ###
        contextualize_q_system_prompt = """Given a chat history and the latest user question \
        which might reference context in the chat history, formulate a standalone question \
        which can be understood without the chat history. Do NOT answer the question, \
        just reformulate it if needed and otherwise return it as is."""
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", contextualize_q_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )
        history_aware_retriever = create_history_aware_retriever(
            llm, retriever, contextualize_q_prompt
        )

        ### Answer question ###
        qa_system_prompt = """You are an assistant for question-answering tasks. \
        Use the following pieces of retrieved context to answer the question. \
        If you don't know the answer, just say that you don't know. \
        Use three sentences maximum and keep the answer concise.\

        {context}"""
        qa_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", qa_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

        rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)


        ### Statefully manage chat history ###
        store = {}

        def get_message_history(session_id: str) -> RedisChatMessageHistory:
            return RedisChatMessageHistory(session_id, url=os.environ["REDIS_URL"])

        conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            get_message_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

        return conversational_rag_chain.invoke(
            {"input": request.message},
            config={
                "configurable": {"session_id": request.id or "default"},
            },
        )["answer"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/input_schema")
async def input_schema() -> dict:
    """Return the input schema of the runnable."""
    return agent.get_input_schema().schema()


@router.get("/output_schema")
async def output_schema() -> dict:
    """Return the output schema of the runnable."""
    return agent.get_output_schema().schema()


@router.get("/config_schema")
async def config_schema() -> dict:
    """Return the config schema of the runnable."""
    return agent.config_schema().schema()


if tracing_is_enabled():
    langsmith_client = langsmith.client.Client()

    @router.post("/feedback")
    def create_run_feedback(feedback_create_req: FeedbackCreateRequest) -> dict:
        """
        Send feedback on an individual run to langsmith

        Note that a successful response means that feedback was successfully
        submitted. It does not guarantee that the feedback is recorded by
        langsmith. Requests may be silently rejected if they are
        unauthenticated or invalid by the server.
        """

        langsmith_client.create_feedback(
            feedback_create_req.run_id,
            feedback_create_req.key,
            score=feedback_create_req.score,
            value=feedback_create_req.value,
            comment=feedback_create_req.comment,
            source_info={
                "from_langserve": True,
            },
        )

        return {"status": "ok"}
