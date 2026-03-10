import {
  createStaticApiFetcher,
  createDynamicApiFetcher,
} from "./create-api-fetcher.ts";
import type {
  GatewayEndpointListItem,
  GatewaySecretListItem,
  GatewayModelListItem,
  EntityPermission,
  BasePatternPermission,
} from "../../shared/types/entity";

// Gateway Lists
export const fetchAllGatewayEndpoints = createStaticApiFetcher<
  GatewayEndpointListItem[]
>({
  endpointKey: "ALL_GATEWAY_ENDPOINTS",
  responseType: [] as GatewayEndpointListItem[],
});

export const fetchAllGatewaySecrets = createStaticApiFetcher<
  GatewaySecretListItem[]
>({
  endpointKey: "ALL_GATEWAY_SECRETS",
  responseType: [] as GatewaySecretListItem[],
});

export const fetchAllGatewayModels = createStaticApiFetcher<
  GatewayModelListItem[]
>({
  endpointKey: "ALL_GATEWAY_MODELS",
  responseType: [] as GatewayModelListItem[],
});

// User Permissions for Gateway Resources
export const fetchUserGatewayEndpointPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "USER_GATEWAY_ENDPOINT_PERMISSIONS"
>({
  endpointKey: "USER_GATEWAY_ENDPOINT_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchUserGatewaySecretPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "USER_GATEWAY_SECRET_PERMISSIONS"
>({
  endpointKey: "USER_GATEWAY_SECRET_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchUserGatewayModelPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "USER_GATEWAY_MODEL_PERMISSIONS"
>({
  endpointKey: "USER_GATEWAY_MODEL_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

// User Pattern Permissions for Gateway Resources
export const fetchUserGatewayEndpointPatternPermissions =
  createDynamicApiFetcher<
    BasePatternPermission[],
    "USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS"
  >({
    endpointKey: "USER_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS",
    responseType: [] as BasePatternPermission[],
  });

export const fetchUserGatewaySecretPatternPermissions = createDynamicApiFetcher<
  BasePatternPermission[],
  "USER_GATEWAY_SECRET_PATTERN_PERMISSIONS"
>({
  endpointKey: "USER_GATEWAY_SECRET_PATTERN_PERMISSIONS",
  responseType: [] as BasePatternPermission[],
});

export const fetchUserGatewayModelPatternPermissions = createDynamicApiFetcher<
  BasePatternPermission[],
  "USER_GATEWAY_MODEL_PATTERN_PERMISSIONS"
>({
  endpointKey: "USER_GATEWAY_MODEL_PATTERN_PERMISSIONS",
  responseType: [] as BasePatternPermission[],
});

// Group Permissions for Gateway Resources
export const fetchGroupGatewayEndpointPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GROUP_GATEWAY_ENDPOINT_PERMISSIONS"
>({
  endpointKey: "GROUP_GATEWAY_ENDPOINT_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGroupGatewaySecretPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GROUP_GATEWAY_SECRET_PERMISSIONS"
>({
  endpointKey: "GROUP_GATEWAY_SECRET_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGroupGatewayModelPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GROUP_GATEWAY_MODEL_PERMISSIONS"
>({
  endpointKey: "GROUP_GATEWAY_MODEL_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

// Group Pattern Permissions for Gateway Resources
export const fetchGroupGatewayEndpointPatternPermissions =
  createDynamicApiFetcher<
    BasePatternPermission[],
    "GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS"
  >({
    endpointKey: "GROUP_GATEWAY_ENDPOINT_PATTERN_PERMISSIONS",
    responseType: [] as BasePatternPermission[],
  });

export const fetchGroupGatewaySecretPatternPermissions =
  createDynamicApiFetcher<
    BasePatternPermission[],
    "GROUP_GATEWAY_SECRET_PATTERN_PERMISSIONS"
  >({
    endpointKey: "GROUP_GATEWAY_SECRET_PATTERN_PERMISSIONS",
    responseType: [] as BasePatternPermission[],
  });

export const fetchGroupGatewayModelPatternPermissions = createDynamicApiFetcher<
  BasePatternPermission[],
  "GROUP_GATEWAY_MODEL_PATTERN_PERMISSIONS"
>({
  endpointKey: "GROUP_GATEWAY_MODEL_PATTERN_PERMISSIONS",
  responseType: [] as BasePatternPermission[],
});

// Resource User Permissions
export const fetchGatewayEndpointUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GATEWAY_ENDPOINT_USER_PERMISSIONS"
>({
  endpointKey: "GATEWAY_ENDPOINT_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGatewaySecretUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GATEWAY_SECRET_USER_PERMISSIONS"
>({
  endpointKey: "GATEWAY_SECRET_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGatewayModelUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GATEWAY_MODEL_USER_PERMISSIONS"
>({
  endpointKey: "GATEWAY_MODEL_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

// Resource Group Permissions
export const fetchGatewayEndpointGroupPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GATEWAY_ENDPOINT_GROUP_PERMISSIONS"
>({
  endpointKey: "GATEWAY_ENDPOINT_GROUP_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGatewaySecretGroupPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GATEWAY_SECRET_GROUP_PERMISSIONS"
>({
  endpointKey: "GATEWAY_SECRET_GROUP_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGatewayModelGroupPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GATEWAY_MODEL_GROUP_PERMISSIONS"
>({
  endpointKey: "GATEWAY_MODEL_GROUP_PERMISSIONS",
  responseType: [] as EntityPermission[],
});
