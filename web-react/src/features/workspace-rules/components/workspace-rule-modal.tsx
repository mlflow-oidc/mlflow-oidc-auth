import React, { useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";
import { Select } from "../../../shared/components/select";
import { Switch } from "../../../shared/components/switch";
import { Button } from "../../../shared/components/button";
import { useToast } from "../../../shared/components/toast/use-toast";
import { extractErrorMessage } from "../../../core/services/http";
import {
  createWorkspaceRule,
  previewUnsavedWorkspaceRule,
  previewWorkspaceRule,
  updateWorkspaceRule,
} from "../../../core/services/workspace-rule-service";
import type {
  WorkspaceRule,
  WorkspaceRuleChange,
  WorkspaceRuleCreateRequest,
  WorkspaceRuleMode,
  WorkspaceRulePermission,
  WorkspaceRulePlan,
  WorkspaceRuleUpdateRequest,
} from "../../../shared/types/entity";
import { RulePreview } from "./rule-preview";

interface WorkspaceRuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  /** The rule to edit; null to create one. */
  rule: WorkspaceRule | null;
  /** The permissions the server's ceiling allows, lowest first. */
  allowedPermissions: WorkspaceRulePermission[];
  maxPermission: WorkspaceRulePermission | null;
}

const MODE_OPTIONS: { label: string; value: WorkspaceRuleMode }[] = [
  {
    label: "Report — show what it would grant, write nothing",
    value: "report",
  },
  { label: "Enforce — grant workspace permissions", value: "enforce" },
];

const PREVIEW_CAPTION =
  "Preview — nothing has been written. This is what enforcing the rule would do now.";

function initialForm(
  rule: WorkspaceRule | null,
  allowed: WorkspaceRulePermission[],
): WorkspaceRuleCreateRequest {
  if (rule) {
    return {
      name: rule.name,
      pattern: rule.pattern,
      permission: rule.permission,
      mode: rule.mode,
      enabled: rule.enabled,
    };
  }
  return {
    name: "",
    pattern: "",
    permission: allowed.includes("READ") ? "READ" : (allowed[0] ?? "READ"),
    // A new rule reports first: the admin sees what it would do before it does it.
    mode: "report",
    enabled: true,
  };
}

/** Only the fields the admin changed, so an untouched permission above a lowered ceiling is not re-sent. */
function changedFields(
  rule: WorkspaceRule,
  form: WorkspaceRuleCreateRequest,
): WorkspaceRuleUpdateRequest {
  const changes: WorkspaceRuleUpdateRequest = {};
  if (form.name.trim() !== rule.name) changes.name = form.name.trim();
  if (form.pattern !== rule.pattern) changes.pattern = form.pattern;
  if (form.permission !== rule.permission) changes.permission = form.permission;
  if (form.mode !== rule.mode) changes.mode = form.mode;
  if (form.enabled !== rule.enabled) changes.enabled = form.enabled;
  return changes;
}

function summarize(
  verb: string,
  name: string,
  changes: WorkspaceRuleChange[],
): string {
  const written = changes.filter((c) => c.applied).length;
  return written > 0
    ? `Rule "${name}" ${verb}: ${written} workspace permission change(s) written`
    : `Rule "${name}" ${verb}: nothing written`;
}

export const WorkspaceRuleModal: React.FC<WorkspaceRuleModalProps> = (
  props,
) => (
  // Remounted on every open, so the form starts from the rule being edited.
  <Modal
    isOpen={props.isOpen}
    onClose={props.onClose}
    title={props.rule ? "Edit workspace rule" : "Create workspace rule"}
    width="max-w-3xl"
  >
    {props.isOpen && (
      <WorkspaceRuleForm key={props.rule?.id ?? "new"} {...props} />
    )}
  </Modal>
);

const WorkspaceRuleForm: React.FC<WorkspaceRuleModalProps> = ({
  onClose,
  onSuccess,
  rule,
  allowedPermissions,
  maxPermission,
}) => {
  const { showToast } = useToast();
  const [form, setForm] = useState<WorkspaceRuleCreateRequest>(() =>
    initialForm(rule, allowedPermissions),
  );
  const [nameError, setNameError] = useState<string | undefined>();
  const [serverError, setServerError] = useState<string | null>(null);
  const [preview, setPreview] = useState<WorkspaceRulePlan | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const aboveCeiling =
    rule !== null && !allowedPermissions.includes(rule.permission);
  const permissionOptions = [
    ...allowedPermissions.map((p) => ({ label: p, value: p })),
    ...(aboveCeiling && rule
      ? [
          {
            label: `${rule.permission} (above the ${maxPermission ?? ""} ceiling)`,
            value: rule.permission,
          },
        ]
      : []),
  ];

  const update = <K extends keyof WorkspaceRuleCreateRequest>(
    key: K,
    value: WorkspaceRuleCreateRequest[K],
  ) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setServerError(null);
    // A preview describes the pattern and permission it was made for.
    if (key === "pattern" || key === "permission") setPreview(null);
  };

  const handlePreview = async () => {
    setIsPreviewing(true);
    setServerError(null);
    try {
      const unchanged =
        rule !== null &&
        form.pattern === rule.pattern &&
        form.permission === rule.permission;
      const plan = unchanged
        ? await previewWorkspaceRule(rule.id)
        : await previewUnsavedWorkspaceRule({
            pattern: form.pattern,
            permission: form.permission,
          });
      setPreview(plan);
    } catch (err) {
      setServerError(extractErrorMessage(err, "Failed to preview the rule"));
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setNameError("Name is required");
      return;
    }
    setNameError(undefined);
    setIsSubmitting(true);
    setServerError(null);
    try {
      if (rule) {
        const changes = changedFields(rule, form);
        if (Object.keys(changes).length === 0) {
          onClose();
          return;
        }
        const plan = await updateWorkspaceRule(rule.id, changes);
        showToast(
          summarize("saved", form.name.trim(), plan.changes),
          "success",
        );
      } else {
        const plan = await createWorkspaceRule({
          ...form,
          name: form.name.trim(),
        });
        showToast(
          summarize("created", form.name.trim(), plan.changes),
          "success",
        );
      }
      onSuccess();
      onClose();
    } catch (err) {
      const message = extractErrorMessage(err, "Failed to save the rule");
      setServerError(message);
      showToast(message, "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      aria-label={
        rule ? "Edit workspace rule form" : "Create workspace rule form"
      }
    >
      <Input
        label="Name"
        id="workspace-rule-name"
        value={form.name}
        onChange={(e) => update("name", e.target.value)}
        error={nameError}
        required
        reserveErrorSpace
        containerClassName="mb-2"
      />

      <Input
        label="Group name pattern"
        id="workspace-rule-pattern"
        value={form.pattern}
        onChange={(e) => update("pattern", e.target.value)}
        placeholder="^team-(?P<ws>[a-z0-9-]+)$"
        className="font-mono"
        required
        containerClassName="mb-1"
      />
      <p className="mb-3 text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
        A Python regular expression that must match the whole group name. The
        named group <code>(?P&lt;ws&gt;…)</code> is the workspace. Groups from a
        provider other than the default one carry its prefix, e.g.{" "}
        <code>partner:team-acme</code>.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Select
          label="Permission"
          id="workspace-rule-permission"
          value={form.permission}
          options={permissionOptions}
          onChange={(e) =>
            update("permission", e.target.value as WorkspaceRulePermission)
          }
          reserveErrorSpace
        />
        <Select
          label="Mode"
          id="workspace-rule-mode"
          value={form.mode}
          options={MODE_OPTIONS}
          onChange={(e) => update("mode", e.target.value as WorkspaceRuleMode)}
          reserveErrorSpace
        />
      </div>
      {maxPermission && (
        <p className="mb-3 -mt-2 text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
          The server allows rules up to {maxPermission}{" "}
          (WORKSPACE_RULES_MAX_PERMISSION).
        </p>
      )}

      <Switch
        checked={form.enabled}
        onChange={(checked) => update("enabled", checked)}
        label="Enabled"
        className="mb-4"
      />

      <div className="mb-4">
        <Button
          type="button"
          variant="secondary"
          onClick={() => void handlePreview()}
          disabled={isPreviewing || !form.pattern}
        >
          {isPreviewing ? "Previewing..." : "Preview"}
        </Button>
        {preview && (
          <div className="mt-3">
            <RulePreview changes={preview.changes} caption={PREVIEW_CAPTION} />
          </div>
        )}
      </div>

      {serverError && (
        <p role="alert" className="mb-3 text-sm text-red-500 break-words">
          {serverError}
        </p>
      )}

      <div className="flex justify-end space-x-3 pt-2">
        <Button
          type="button"
          onClick={onClose}
          variant="ghost"
          disabled={isSubmitting}
        >
          Cancel
        </Button>
        <Button type="submit" variant="primary" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : rule ? "Save" : "Create"}
        </Button>
      </div>
    </form>
  );
};
