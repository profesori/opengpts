import { Config } from "../hooks/useConfigList";
import { getCookie } from "../utils/cookie";

export async function getAssistant(
  assistantId: string,
): Promise<Config | null> {
  try {
    const opengpts_user_id = getCookie("opengpts_user_id");

    const response = await fetch(`/assistants/${assistantId}`, {
      headers: {
        Authorization: `Bearer ${opengpts_user_id}`,
      },
    
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as Config;
  } catch (error) {
    console.error("Failed to fetch assistant:", error);
    return null;
  }
}
