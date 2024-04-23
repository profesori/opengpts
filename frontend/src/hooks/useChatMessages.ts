import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Message } from "../types";
import { StreamState, mergeMessagesById } from "./useStreamState";
import { getCookie } from "../utils/cookie";

async function getState(threadId: string, opengpts_user_id: string | undefined) {
  const { values, next } = await fetch(`/threads/${threadId}/state`, {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${opengpts_user_id}`,
    },
  }).then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)));
  return { values, next };
}

function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>();
  useEffect(() => {
    ref.current = value;
  });
  return ref.current;
}

export function useChatMessages(
  threadId: string | null,
  stream: StreamState | null,
  stopStream?: (clear?: boolean) => void,
) {
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [next, setNext] = useState<string[]>([]);
  const prevStreamStatus = usePrevious(stream?.status);

  const opengpts_user_id = getCookie('opengpts_user_id');

  const refreshMessages = useCallback(async () => {
    if (threadId) {
      const { values, next } = await getState(threadId, opengpts_user_id);
      const messages = values
        ? Array.isArray(values)
          ? values
          : values.messages
        : [];
      setMessages(messages);
      setNext(next);
    }
  }, [threadId, opengpts_user_id]);

  useEffect(() => {
    refreshMessages();
    return () => {
      setMessages(null);
    };
  }, [threadId, refreshMessages]);

  useEffect(() => {
    async function fetchMessages() {
      if (threadId) {
        const { values, next } = await getState(threadId, opengpts_user_id);
        const messages = Array.isArray(values) ? values : values.messages;
        setMessages(messages);
        setNext(next);
        stopStream?.(true);
      }
    }

    if (prevStreamStatus === "inflight" && stream?.status !== "inflight") {
      setNext([]);
      fetchMessages();
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream?.status, opengpts_user_id]);

  return useMemo(
    () => ({
      refreshMessages,
      messages: mergeMessagesById(messages, stream?.messages),
      next,
    }),
    [messages, stream?.messages, next, refreshMessages],
  );
}