import { useEffect, useState } from "react";
import { simplifySchema } from "../utils/simplifySchema";
import { getDefaults } from "../utils/defaults";
import { getCookie } from "../utils/cookie";

export interface SchemaField {
  type: string;
  title: string;
  description: string;
  enum?: string[];
  items?: SchemaField;
  allOf?: SchemaField[];
}

export interface Schemas {
  configSchema: null | {
    properties: {
      configurable: {
        properties: {
          [key: string]: SchemaField;
        };
      };
    };
  };
  configDefaults: null | {
    configurable?: {
      [key: string]: unknown;
    };
  };
}

export function useSchemas() {
  const [schemas, setSchemas] = useState<Schemas>({
    configSchema: null,
    configDefaults: null,
  });

  useEffect(() => {
    async function save() {
      const opengpts_user_id = getCookie("opengpts_user_id");

      const configSchema = await fetch("/runs/config_schema", {
        headers: {
          "Authorization": `Bearer ${opengpts_user_id}`,
        }
      })
        .then((r) => r.json())
        .then(simplifySchema);
      setSchemas({
        configSchema,
        configDefaults: getDefaults(configSchema) as Record<string, unknown>,
      });
    }

    save();
  }, []);

  return schemas;
}
