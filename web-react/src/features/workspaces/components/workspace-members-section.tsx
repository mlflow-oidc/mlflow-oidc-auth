import { useState } from "react";
import { faEdit, faTrash } from "@fortawesome/free-solid-svg-icons";
import { IconButton } from "../../../shared/components/icon-button";
import { Modal } from "../../../shared/components/modal";
import { PermissionLevelSelect } from "../../../shared/components/permission-level-select";
import { Button } from "../../../shared/components/button";
import PageStatus from "../../../shared/components/page/page-status";
import { useToast } from "../../../shared/components/toast/use-toast";
import type { PermissionLevel } from "../../../shared/types/entity";

interface WorkspaceMembersSectionProps {
  title: string;
  members: Array<{ name: string; permission: PermissionLevel }>;
  isLoading: boolean;
  error: Error | null;
  onUpdate: (name: string, permission: PermissionLevel) => Promise<void>;
  onRemove: (name: string) => Promise<void>;
  onRefresh: () => void;
  nameLabel: string;
  canManage: boolean;
}

export default function WorkspaceMembersSection({
  title,
  members,
  isLoading,
  error,
  onUpdate,
  onRemove,
  onRefresh,
  nameLabel,
  canManage,
}: WorkspaceMembersSectionProps) {
  const { showToast } = useToast();
  const [editingMember, setEditingMember] = useState<{ name: string; permission: PermissionLevel } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [editPermission, setEditPermission] = useState<PermissionLevel>("READ");

  const handleEditClick = (member: { name: string; permission: PermissionLevel }) => {
    setEditingMember(member);
    setEditPermission(member.permission);
  };

  const handleEditSave = async () => {
    if (!editingMember) return;
    setIsSaving(true);
    try {
      await onUpdate(editingMember.name, editPermission);
      setEditingMember(null);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemove = async (name: string) => {
    try {
      await onRemove(name);
    } catch {
      showToast("Failed to remove member", "error");
    }
  };

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-ui-text dark:text-ui-text-dark">
          {title} ({members.length})
        </h2>
      </div>

      <PageStatus isLoading={isLoading} loadingText={`Loading ${title.toLowerCase()}...`} error={error} onRetry={onRefresh} />

      {!isLoading && !error && (
        <>
          {members.length === 0 ? (
            <p className="text-sm text-ui-text dark:text-ui-text-dark opacity-60">No {title.toLowerCase()} assigned.</p>
          ) : (
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-ui-border dark:border-ui-border-dark">
                  <th className="py-2 px-3 font-medium text-ui-text dark:text-ui-text-dark">{nameLabel}</th>
                  <th className="py-2 px-3 font-medium text-ui-text dark:text-ui-text-dark">Permission</th>
                  {canManage && (
                    <th className="py-2 px-3 font-medium text-ui-text dark:text-ui-text-dark w-24">Actions</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.name} className="border-b border-ui-border dark:border-ui-border-dark">
                    <td className="py-2 px-3 text-ui-text dark:text-ui-text-dark">{member.name}</td>
                    <td className="py-2 px-3 text-ui-text dark:text-ui-text-dark">{member.permission}</td>
                    {canManage && (
                      <td className="py-2 px-3">
                        <div className="flex space-x-2">
                          <IconButton icon={faEdit} title="Edit permission" onClick={() => handleEditClick(member)} />
                          <IconButton icon={faTrash} title="Remove member" onClick={() => void handleRemove(member.name)} />
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {editingMember && (
        <Modal isOpen={!!editingMember} onClose={() => setEditingMember(null)} title={`Edit Permission for ${editingMember.name}`}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">{nameLabel}</label>
            <input
              type="text"
              value={editingMember.name}
              disabled
              className="w-full px-3 py-2 border rounded-md text-ui-text dark:text-ui-text-dark bg-ui-bg dark:bg-ui-bg-dark border-ui-border dark:border-ui-border-dark opacity-70 cursor-not-allowed"
            />
          </div>

          <PermissionLevelSelect id="edit-permission-level" label="Permission" value={editPermission} onChange={(val) => setEditPermission(val)} required containerClassName="mb-4" />

          <div className="flex justify-end space-x-3">
            <Button onClick={() => setEditingMember(null)} variant="ghost" disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={() => void handleEditSave()} variant="primary" disabled={isSaving}>
              {isSaving ? "Saving..." : "Save"}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
