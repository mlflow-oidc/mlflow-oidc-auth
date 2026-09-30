import React, { useRef, useState } from "react";
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
) => {
  const [isBusy, setIsBusy] = useState(false);
  const { onClose } = props;
  return (
    // Remounted on every open, so the form starts from the rule being edited. While a save is in
    // flight, Escape, the close button and the backdrop do nothing: the result must land in view.
    <Modal
      isOpen={props.isOpen}
      onClose={isBusy ? () => undefined : onClose}
      title={props.rule ? "Edit workspace rule" : "Create workspace rule"}
      width="max-w-3xl"
    >
      {props.isOpen && (
        <WorkspaceRuleForm
          key={props.rule?.id ?? "new"}
          {...props}
          onBusyChange={setIsBusy}
        />
      )}
    </Modal>
  );
};

const WorkspaceRuleForm: React.FC<
  WorkspaceRuleModalProps & { onBusyChange: (busy: boolean) => void }
> = ({
  onClose,
  onSuccess,
  rule,
  allowedPermissions,
  maxPermission,
  onBusyChange,
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
  // Only the newest preview may land: a slower, older one describes a pattern no longer in the form.
  const previewRequest = useRef(0);

  const aboveCeiling =
    rule !== null && !allowedPermissions.includes(rule.permission);
  // The server refuses to preview or save a permission above its ceiling.
  const permissionAllowed = allowedPermissions.includes(form.permission);
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
    if (key === "pattern" || key === "permission") {
      previewRequest.current += 1;
      setPreview(null);
      setIsPreviewing(false);
    }
  };

  const handlePreview = async () => {
    const request = ++previewRequest.current;
    const isCurrent = () => request === previewRequest.current;
    setIsPreviewing(true);
    setServerError(null);
    try {
      const unchanged =
        rule !== null &&
        form.pattern === rule.pattern &&
        form.permission === rule.permission;
      // Changes to a saved rule are previewed under its own id, so it keeps its precedence and
      // its existing grants show as unchanged or updated rather than as another rule's.
      const plan = unchanged
        ? await previewWorkspaceRule(rule.id)
        : await previewUnsavedWorkspaceRule({
            pattern: form.pattern,
            permission: form.permission,
            ...(rule ? { rule_id: rule.id } : {}),
          });
      if (isCurrent()) setPreview(plan);
    } catch (err) {
      if (isCurrent()) {
        setServerError(extractErrorMessage(err, "Failed to preview the rule"));
      }
    } finally {
      if (isCurrent()) setIsPreviewing(false);
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
    onBusyChange(true);
    setServerError(null);
    try {
      if (rule) {
        const changes = changedFields(rule, form);
        if (Object.keys(changes).length === 0) {
          onClose();
          return;
        }
        report(await updateWorkspaceRule(rule.id, changes), "saved");
      } else {
        const plan = await createWorkspaceRule({
          ...form,
          name: form.name.trim(),
        });
        report(plan, "created");
      }
      onSuccess();
      onClose();
    } catch (err) {
      const message = extractErrorMessage(err, "Failed to save the rule");
      setServerError(message);
      showToast(message, "error");
    } finally {
      setIsSubmitting(false);
      onBusyChange(false);
    }
  };

  const report = (plan: WorkspaceRulePlan, verb: string) => {
    if (plan.error) {
      // Saved, but its grants were not updated: say so rather than a plain success.
      showToast(`Rule "${form.name.trim()}" ${verb}. ${plan.error}`, "error");
      return;
    }
    showToast(summarize(verb, form.name.trim(), plan.changes), "success");
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
        maxLength={255}
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
        maxLength={256}
        aria-describedby="workspace-rule-pattern-help"
        required
        containerClassName="mb-1"
      />
      <p
        id="workspace-rule-pattern-help"
        className="mb-3 text-xs text-ui-text-muted dark:text-ui-text-muted-dark"
      >
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
          disabled={isPreviewing || !form.pattern || !permissionAllowed}
        >
          {isPreviewing ? "Previewing..." : "Preview"}
        </Button>
        {!permissionAllowed && (
          <p className="mt-1 text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
            Choose a permission within the ceiling to preview.
          </p>
        )}
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
