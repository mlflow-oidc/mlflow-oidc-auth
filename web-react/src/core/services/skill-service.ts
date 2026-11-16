import {
  createDynamicApiFetcher,
  createStaticApiFetcher,
} from "./create-api-fetcher.ts";
import { createPagedFetcher } from "./paged-list";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";
import type {
  EntityPermission,
  SkillListItem,
} from "../../shared/types/entity";

// Every skill the caller may manage, unpaginated (grant pickers)
export const fetchAllSkills = createStaticApiFetcher<SkillListItem[]>({
  endpointKey: "ALL_SKILLS",
  responseType: [] as SkillListItem[],
});

// skills of the request's workspace the caller may manage (all of them for an admin).
export const fetchSkillsPage = createPagedFetcher<
  SkillListItem[],
  SkillListItem
>(STATIC_API_ENDPOINTS.ALL_SKILLS, {
  extract: (body) => body ?? [],
  displayKey: (skill) => skill.name,
});

// Users and groups holding a grant on one skill
export const fetchSkillUserPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "SKILL_USER_PERMISSIONS"
>({
  endpointKey: "SKILL_USER_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchSkillGroupPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "SKILL_GROUP_PERMISSIONS"
>({
  endpointKey: "SKILL_GROUP_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

// A user's / a group's skill permissions (there is no pattern API for skills)
export const fetchUserSkillPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "USER_SKILL_PERMISSIONS"
>({
  endpointKey: "USER_SKILL_PERMISSIONS",
  responseType: [] as EntityPermission[],
});

export const fetchGroupSkillPermissions = createDynamicApiFetcher<
  EntityPermission[],
  "GROUP_SKILL_PERMISSIONS"
>({
  endpointKey: "GROUP_SKILL_PERMISSIONS",
  responseType: [] as EntityPermission[],
});
