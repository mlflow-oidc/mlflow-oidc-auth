import { DYNAMIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";
import type { PermissionType } from "../../../shared/types/entity";

interface GetPermissionUrlParams {
  entityKind: "user" | "group";
  entityName: string;
  type: PermissionType;
  isPattern?: boolean;
  identifier?: string;
}

export const getPermissionUrl = ({
  entityKind,
  entityName,
  type,
  isPattern = false,
  identifier,
}: GetPermissionUrlParams): string => {
  if (isPattern) {
    if (identifier) {
      // Single pattern permission (GET, PATCH, DELETE)
      if (type === "experiments") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PATTERN_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PATTERN_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "models") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_MODEL_PATTERN_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PATTERN_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "prompts") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_PROMPT_PATTERN_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PATTERN_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "ai-endpoints") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PATTERN_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "ai-secrets") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PATTERN_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PATTERN_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "ai-models") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PATTERN_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PATTERN_PERMISSION(
              entityName,
              identifier,
            );
      }
    } else {
      // Pattern permissions collection (POST to create)
      if (type === "experiments") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PATTERN_PERMISSIONS(
              entityName,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PATTERN_PERMISSIONS(
              entityName,
            );
      }
      if (type === "models") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_MODEL_PATTERN_PERMISSIONS(entityName)
          : DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PATTERN_PERMISSIONS(entityName);
      }
      if (type === "prompts") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_PROMPT_PATTERN_PERMISSIONS(entityName)
          : DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PATTERN_PERMISSIONS(entityName);
      }
      if (type === "ai-endpoints") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS(
              entityName,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS(
              entityName,
            );
      }
      if (type === "ai-secrets") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PATTERN_PERMISSIONS(
              entityName,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PATTERN_PERMISSIONS(
              entityName,
            );
      }
      if (type === "ai-models") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PATTERN_PERMISSIONS(
              entityName,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PATTERN_PERMISSIONS(
              entityName,
            );
      }
    }
  } else {
    // Normal permissions
    if (identifier) {
      if (type === "experiments") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "models") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSION(entityName, identifier)
          : DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "prompts") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(entityName, identifier)
          : DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "ai-endpoints") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "ai-secrets") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PERMISSION(
              entityName,
              identifier,
            );
      }
      if (type === "ai-models") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PERMISSION(
              entityName,
              identifier,
            )
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PERMISSION(
              entityName,
              identifier,
            );
      }
    } else {
      // Normal permissions collection
      if (type === "experiments") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSIONS(entityName)
          : DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSIONS(entityName);
      }
      if (type === "models") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSIONS(entityName)
          : DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSIONS(entityName);
      }
      if (type === "prompts") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSIONS(entityName)
          : DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSIONS(entityName);
      }
      if (type === "ai-endpoints") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PERMISSIONS(entityName)
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PERMISSIONS(
              entityName,
            );
      }
      if (type === "ai-secrets") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PERMISSIONS(entityName)
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PERMISSIONS(entityName);
      }
      if (type === "ai-models") {
        return entityKind === "user"
          ? DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PERMISSIONS(entityName)
          : DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PERMISSIONS(entityName);
      }
    }
  }

  throw new Error("Unknown permission type");
};
