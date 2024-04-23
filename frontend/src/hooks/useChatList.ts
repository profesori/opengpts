import { useCallback, useEffect, useReducer } from "react";
import orderBy from "lodash/orderBy";
import { Chat } from "../types";
import { getCookie } from "../utils/cookie";

export interface ChatListProps {
  chats: Chat[] | null;
  createChat: (
    name: string,
    assistant_id: string,
    thread_id?: string,
  ) => Promise<Chat>;
  deleteChat: (thread_id: string) => Promise<void>;
}

function chatsReducer(
  state: Chat[] | null,
  action: Chat | Chat[],
): Chat[] | null {
  state = state ?? [];
  if (!Array.isArray(action)) {
    const newChat = action;
    action = [
      ...state.filter((c) => c.thread_id !== newChat.thread_id),
      newChat,
    ];
  }
  return orderBy(action, "updated_at", "desc");
}

export function useChatList(): ChatListProps {
  const [chats, setChats] = useReducer(chatsReducer, null);

  const opengpts_user_id = getCookie('opengpts_user_id');

  useEffect(() => {
    async function fetchChats() {
      const chats = await fetch("/threads/", {
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${opengpts_user_id}`,
        },
      }).then((r) => r.json());
      setChats(chats);
    }

    fetchChats();
  }, []);

  const createChat = useCallback(async (name: string, assistant_id: string) => {
    const response = await fetch(`/threads`, {
      method: "POST",
      body: JSON.stringify({ assistant_id, name }),
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${opengpts_user_id}`,
      },
    });
    const saved = await response.json();
    setChats(saved);
    return saved;
  }, []);

  const deleteChat = useCallback(
    async (thread_id: string) => {
      await fetch(`/threads/${thread_id}`, {
        method: "DELETE",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${opengpts_user_id}`,
        },
      });
      setChats((chats || []).filter((c: Chat) => c.thread_id !== thread_id));
    },
    [chats],
  );

  return {
    chats,
    createChat,
    deleteChat,
  };
}