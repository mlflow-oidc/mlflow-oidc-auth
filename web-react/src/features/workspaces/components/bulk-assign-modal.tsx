import { useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { PermissionLevelSelect } from "../../../shared/components/permission-level-select";
import { useToast } from "../../../shared/components/toast/use-toast";
import type { PermissionLevel } from "../../../shared/types/entity";

interface BulkAssignModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGrant: (name: string, permission: PermissionLevel) => Promise<boolean>;
  onSuccess: () => void;
  title: string;
  nameLabel: string;
  namePlaceholder: string;
}

interface BulkAssignResult {
  name: string;
  success: boolean;
}

export function BulkAssignModal({ isOpen, onClose, onGrant, onSuccess, title, nameLabel, namePlaceholder }: BulkAssignModalProps) {
  const { showToast } = useToast();
  const [namesInput, setNamesInput] = useState("");
  const [permission, setPermission] = useState<PermissionLevel>("READ");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [results, setResults] = useState<BulkAssignResult[] | null>(null);

  const handleNamesChange = (value: string) => {
    setNamesInput(value);
    setResults(null);
  };

  const parseNames = (input: string): string[] => {
    const names = input
      .split(/[,\n]/)
      .map((n) => n.trim())
      .filter((n) => n.length > 0);
    return [...new Set(names)];
  };

  const handleSubmit = async () => {
    const names = parseNames(namesInput);
    if (names.length === 0) {
      showToast("No names provided", "error");
      return;
    }

    setIsSubmitting(true);
    const collected: BulkAssignResult[] = [];

    for (const name of names) {
      const success = await onGrant(name, permission);
      collected.push({ name, success });
    }

    setResults(collected);
    const successes = collected.filter((r) => r.success).length;
    const failures = collected.filter((r) => !r.success).length;

    if (failures === 0) {
      showToast(`Successfully assigned ${successes} permissions`, "success");
      onSuccess();
      onClose();
    } else {
      showToast(`${successes} assigned, ${failures} failed`, "error");
      onSuccess();
    }

    setIsSubmitting(false);
  };

  const failedNames = results?.filter((r) => !r.success).map((r) => r.name) ?? [];
  const successCount = results?.filter((r) => r.success).length ?? 0;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} width="max-w-lg">
      <div key={isOpen ? "open" : "closed"}>
        <div className="mb-4">
          <label htmlFor="bulk-names" className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
            {nameLabel}*
          </label>
          <textarea
            id="bulk-names"
            value={namesInput}
            onChange={(e) => handleNamesChange(e.target.value)}
            placeholder={namePlaceholder}
            rows={4}
            className="w-full px-3 py-2 border rounded-md focus:outline-none text-ui-text dark:text-ui-text-dark bg-ui-bg dark:bg-ui-bg-dark border-ui-border dark:border-ui-border-dark focus:border-btn-primary dark:focus:border-btn-primary-dark transition duration-150 ease-in-out"
          />
          <p className="mt-1 text-xs text-ui-text dark:text-ui-text-dark opacity-60">Enter names separated by commas or newlines</p>
        </div>

        <PermissionLevelSelect id="bulk-permission-level" label="Permission" value={permission} onChange={(val) => setPermission(val)} required containerClassName="mb-4" />

        {results !== null && (
          <div className="mb-4 p-3 rounded-md bg-ui-bg dark:bg-ui-bg-dark border border-ui-border dark:border-ui-border-dark">
            {successCount > 0 && <p className="text-sm text-green-600 dark:text-green-400">✓ {successCount} assigned successfully</p>}
            {failedNames.length > 0 && <p className="text-sm text-red-600 dark:text-red-400">✗ {failedNames.length} failed: {failedNames.join(", ")}</p>}
          </div>
        )}

        <div className="flex justify-end space-x-3">
          <Button onClick={onClose} variant="ghost" disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={() => void handleSubmit()} variant="primary" disabled={isSubmitting || namesInput.trim().length === 0}>
            {isSubmitting ? "Assigning..." : "Assign All"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
