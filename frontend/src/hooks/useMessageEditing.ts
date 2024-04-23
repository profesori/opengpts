import { useCallback, useState } from "react";
import { Message } from "../types";
import { omit } from "lodash";
import { getCookie } from "../utils/cookie";

export function useMessageEditing(
  threadId: string | undefined,
  onSuccess: () => void,
) {
  const [editing, setEditing] = useState<Record<string, Message>>({});

  const recordEdits = useCallback((msg: Message) => {
    setEditing((current) => ({ ...current, [msg.id]: msg }));
  }, []);
  const commitEdits = useCallback(async () => {
    if (!threadId) return;
    const opengpts_user_id = getCookie("opengpts_user_id");

    fetch(`/threads/${threadId}/state`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${opengpts_user_id}`},
      body: JSON.stringify({ values: Object.values(editing) }),
    })
      .then((res) => {
        if (res.ok) {
          setEditing({});
          onSuccess();
        } else {
          return Promise.reject(res.statusText);
        }
      })
      .catch((e) => {
        console.error(e);
      });
  }, [threadId, editing, onSuccess]);
  const abandonEdits = useCallback((msg?: Message) => {
    if (msg) {
      setEditing((current) => {
        return omit(current, msg.id);
      });
    } else {
      setEditing({});
    }
  }, []);

  return {
    editing,
    recordEdits,
    commitEdits: threadId ? commitEdits : undefined,
    abandonEdits,
  };
}
