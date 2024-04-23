import { Chat } from "../types";
import { getCookie } from "../utils/cookie";

export async function getThread(threadId: string): Promise<Chat | null> {
  try {
    const opengpts_user_id = getCookie("opengpts_user_id");

    const response = await fetch(`/threads/${threadId}`, {
      headers: {
        Authorization: `Bearer ${opengpts_user_id}`,
      },
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as Chat;
  } catch (error) {
    console.error("Failed to fetch assistant:", error);
    return null;
  }
}
