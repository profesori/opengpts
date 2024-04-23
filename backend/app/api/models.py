from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union

class Message(BaseModel):
    role: str
    content: str

class Transcriber(BaseModel):
    provider: str
    model: str
    keywords: List[str]
    language: str

class InnerModel(BaseModel):
    provider: str
    url: str
    urlRequestMetadataEnabled: bool
    model: str
    temperature: float
    maxTokens: int
    functions: List
    messages: List[Optional[Message]]
    systemPrompt: str

class Voice(BaseModel):
    provider: str
    voiceId: str

class Call(BaseModel):
    type: str
    callId: str
    orgId: str
    transcriber: Transcriber
    model: InnerModel
    voice: Voice
    credentials: List
    serverUrl: str
    serverUrlSecret: str
    firstMessage: str
    endCallMessage: str
    endCallPhrases: List[str]
    recordingEnabled: bool
    endCallFunctionEnabled: bool
    fillersEnabled: bool
    hipaaEnabled: bool
    liveTranscriptsEnabled: bool
    silenceTimeoutSeconds: int
    responseDelaySeconds: float
    llmRequestDelaySeconds: float
    clientMessages: List[str]
    serverMessages: List[str]
    interruptionsEnabled: bool
    numWordsToInterruptAssistant: int
    callUrl: str
    maxDurationSeconds: int
    customerJoinTimeoutSeconds: int
    backgroundSound: str
    metadata: Dict[str, Union[str, int]]
    miscellaneous: Dict[str, Optional[object]]
    sampleRate: int
    voicemailMessage: str
    voicemailDetectionEnabled: bool
    orgName: str
    id: str
    createdAt: str
    updatedAt: str
    webCallUrl: str
    status: str
    assistantId: str

class CreateVapiRunPayload(BaseModel):
    """Payload for creating a vapi run."""
    model: str
    messages: List[Message]
    temperature: float
    stream: bool
    max_tokens: int
    call: Call
    metadata: Dict[str, Union[str, int]]