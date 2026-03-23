import { useState } from "react";
import { faEdit, faTrash } from "@fortawesome/free-solid-svg-icons";
import { Button } from "../../../shared/components/button";
import { IconButton } from "../../../shared/components/icon-button";
import { Modal } from "../../../shared/components/modal";
import { PermissionLevelSelect } from "../../../shared/components/permission-level-select";
import PageStatus from "../../../shared/components/page/page-status";
import { useToast } from "../../../shared/components/toast/use-toast";
import type { PermissionLevel } from "../../../shared/types/entity";

interface WorkspaceMembersSectionProps {
  title: string;
  members: Array<{ name: string; permission: PermissionLevel }>;
  isLoading: boolean;
  error: Error | null;
  onGrant: (name: string, permission: PermissionLevel) => Promise<boolean>;
  onUpdate: (name: string, permission: PermissionLevel) => Promise<void>;
  onRemove: (name: string) => Promise<void>;
  onRefresh: () => void;
  nameLabel: string;
  namePlaceholder: string;
}

export default function WorkspaceMembersSection({
  title,
  members,
  isLoading,
  error,
  onGrant,
  onUpdate,
  onRemove,
  onRefresh,
  nameLabel,
  namePlaceholder,
}: WorkspaceMembersSectionProps) {
  const { showToast } = useToast();
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<{ name: string; permission: PermissionLevel } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPermission, setNewPermission] = useState<PermissionLevel>("READ");
  const [editPermission, setEditPermission] = useState<PermissionLevel>("READ");

  const handleAdd = async () => {
    if (!newName.trim()) return;
    setIsSaving(true);
    try {
      const success = await onGrant(newName.trim(), newPermission);
      if (success) {
        setIsAddModalOpen(false);
        setNewName("");
        setNewPermission("READ");
      }
    } finally {
      setIsSaving(false);
    }
  };

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
        <Button variant="secondary" onClick={() => setIsAddModalOpen(true)}>
          + Add {title}
        </Button>
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
                  <th className="py-2 px-3 font-medium text-ui-text dark:text-ui-text-dark w-24">Actions</th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.name} className="border-b border-ui-border dark:border-ui-border-dark">
                    <td className="py-2 px-3 text-ui-text dark:text-ui-text-dark">{member.name}</td>
                    <td className="py-2 px-3 text-ui-text dark:text-ui-text-dark">{member.permission}</td>
                    <td className="py-2 px-3">
                      <div className="flex space-x-2">
                        <IconButton icon={faEdit} title="Edit permission" onClick={() => handleEditClick(member)} />
                        <IconButton icon={faTrash} title="Remove member" onClick={() => void handleRemove(member.name)} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}

      {isAddModalOpen && (
        <Modal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} title={`Add ${title}`}>
          <div className="mb-4">
            <label htmlFor="member-name" className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1">
              {nameLabel}*
            </label>
            <input
              id="member-name"
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder={namePlaceholder}
              className="w-full px-3 py-2 border rounded-md focus:outline-none text-ui-text dark:text-ui-text-dark bg-ui-bg dark:bg-ui-bg-dark border-ui-border dark:border-ui-border-dark focus:border-btn-primary dark:focus:border-btn-primary-dark transition duration-150 ease-in-out"
              required
            />
          </div>

          <PermissionLevelSelect id="add-permission-level" label="Permission" value={newPermission} onChange={(val) => setNewPermission(val)} required containerClassName="mb-4" />

          <div className="flex justify-end space-x-3">
            <Button onClick={() => setIsAddModalOpen(false)} variant="ghost" disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={() => void handleAdd()} variant="primary" disabled={isSaving || !newName.trim()}>
              {isSaving ? "Saving..." : "Save"}
            </Button>
          </div>
        </Modal>
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
