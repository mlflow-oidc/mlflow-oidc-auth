import { request } from "./api-utils";
import {
  STATIC_API_ENDPOINTS,
  DYNAMIC_API_ENDPOINTS,
} from "../configs/api-endpoints";
import type {
  WorkspaceRuleCreateRequest,
  WorkspaceRuleList,
  WorkspaceRulePermission,
  WorkspaceRulePlan,
  WorkspaceRuleUpdateRequest,
} from "../../shared/types/entity";

/** Every rule, lowest id (highest precedence) first, with the permission ceiling. */
export const fetchWorkspaceRules = async (signal?: AbortSignal) =>
  request<WorkspaceRuleList>(STATIC_API_ENDPOINTS.WORKSPACE_RULES, { signal });

/** Create a rule. An `enforce` rule is backfilled by the server before it answers. */
export const createWorkspaceRule = async (data: WorkspaceRuleCreateRequest) =>
  request<WorkspaceRulePlan>(STATIC_API_ENDPOINTS.WORKSPACE_RULES, {
    method: "POST",
    body: JSON.stringify(data),
  });

/** Change a rule; the server reconciles its grants in the same call. */
export const updateWorkspaceRule = async (
  ruleId: number,
  data: WorkspaceRuleUpdateRequest,
) =>
  request<WorkspaceRulePlan>(DYNAMIC_API_ENDPOINTS.WORKSPACE_RULE(ruleId), {
    method: "PATCH",
    body: JSON.stringify(data),
  });

/** Delete a rule and every grant it created. Manual grants stay. */
export const deleteWorkspaceRule = async (ruleId: number) =>
  request<WorkspaceRulePlan>(DYNAMIC_API_ENDPOINTS.WORKSPACE_RULE(ruleId), {
    method: "DELETE",
  });

/** What enforcing a saved rule now would do. Writes nothing. */
export const previewWorkspaceRule = async (ruleId: number) =>
  request<WorkspaceRulePlan>(
    DYNAMIC_API_ENDPOINTS.WORKSPACE_RULE_PREVIEW(ruleId),
    {},
  );

/**
 * What a rule that is not saved yet would do if saved now and enforced. Writes nothing.
 * With `rule_id`, previews unsaved changes to that rule, keeping its precedence and grants.
 */
export const previewUnsavedWorkspaceRule = async (data: {
  pattern: string;
  permission: WorkspaceRulePermission;
  rule_id?: number;
}) =>
  request<WorkspaceRulePlan>(STATIC_API_ENDPOINTS.WORKSPACE_RULES_PREVIEW, {
    method: "POST",
    body: JSON.stringify(data),
  });
